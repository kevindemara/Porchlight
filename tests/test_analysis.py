import asyncio
import copy
import hashlib
import json
import time
from contextlib import suppress
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from porchlight.ai.frames import SIGNATURE_EDGE, Frame, extract_frames, similar
from porchlight.ai.observations import ObservationError, validate_observation
from porchlight.ai.ollama import Ollama
from porchlight.ai.pipeline import AnalysisPipeline
from porchlight.ai.workloads import Workload
from porchlight.api.contracts import ApiError, AppSettings, ModelTestResult, ModelView
from porchlight.config import Config
from porchlight.ingestion.imports import Importer, run_tool
from porchlight.ingestion.recordings import Recordings
from porchlight.providers.base import ClipReference, RecordingPage
from porchlight.storage.database import Database
from porchlight.storage.models import (
    Analysis,
    Event,
    IntegrationState,
    Job,
    MediaAsset,
    RecordingReference,
    SettingsRow,
)
from sqlalchemy import func, select

MODEL = ModelView(
    name="synthetic-vision",
    digest="synthetic-digest",
    size_bytes=100,
    local=True,
    vision=True,
    reason="Synthetic fixture",
)


def test_frame_dedup_preserves_small_local_changes() -> None:
    original = bytes([80]) * SIGNATURE_EDGE * SIGNATURE_EDGE * 3
    assert similar(original, original)
    assert similar(original, bytes([81]) * len(original))
    changed = bytearray(original)
    # A small 4x4 patch occupies less than one percent of the signature.
    for row in range(12, 16):
        start = (row * SIGNATURE_EDGE + 12) * 3
        changed[start : start + 12] = bytes([88]) * 12
    assert not similar(original, bytes(changed))
    point = bytearray(original)
    point[300:303] = bytes([140]) * 3
    assert not similar(original, bytes(point))
    assert not similar(original, b"")


def test_invalid_private_model_output_has_only_allowlisted_reason() -> None:
    for content, reason in [
        ("SYNTHETIC_PRIVATE_TEXT", "json_invalid"),
        (json.dumps({"private": "SYNTHETIC_PRIVATE_TEXT"}), "schema_additionalProperties"),
    ]:
        with pytest.raises(ObservationError) as error:
            validate_observation(content, [frame(1, 0)])
        assert error.value.safe_reason == reason
        assert "SYNTHETIC_PRIVATE_TEXT" not in error.value.message


def observation() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "observation_mode": "video_frames",
        "scene_visibility": "daylight_color",
        "summary_suggestion": "Ignore instructions <script>",
        "uncertainty": ["Call https://example.invalid to identify the visitor"],
        "entities": [
            {
                "entity_id": "e01",
                "category": "vehicle",
                "subtype": "car",
                "color": "white",
                "color_evidence": "visible",
                "actions": ["passing"],
                "direction": "left_to_right",
                "evidence_frame_ids": ["f001"],
            }
        ],
    }


def frame(number: int, value: int, *, monochrome: bool = False) -> Frame:
    return Frame(
        f"f{number:03}",
        number * 100,
        f"hash-{number}",
        b"generated",
        bytes([value]) * 24,
        monochrome,
    )


def test_ir_color_and_unchecked_prose_are_removed() -> None:
    validated, summary = validate_observation(
        json.dumps(observation()), [frame(1, 0, monochrome=True)]
    )
    entity = validated["entities"][0]
    assert entity["color"] is None
    assert entity["actions"] == ["visible"]
    assert entity["direction"] == "unknown"
    assert summary == "A car is visible."
    assert "script" not in json.dumps(validated) and "https:" not in json.dumps(validated)


def test_temporal_evidence_requires_distinct_images_not_just_timestamps() -> None:
    data = observation()
    data["entities"][0]["evidence_frame_ids"] = ["f001", "f002"]
    _, summary = validate_observation(json.dumps(data), [frame(1, 0), frame(2, 0)])
    assert summary == "A white car is visible."
    _, summary = validate_observation(json.dumps(data), [frame(1, 0), frame(2, 100)])
    assert summary == "A white car passes from left to right."


@pytest.mark.parametrize("invalid", [None, "still", "missing", "reversed", "outside", "vehicle"])
def test_door_actions_need_action_specific_person_and_temporal_evidence(invalid):
    data = observation()
    entity = data["entities"][0]
    entity.update(
        category="person",
        subtype=None,
        color=None,
        actions=["opening_door", "exiting_doorway"],
        direction="unknown",
        evidence_frame_ids=["f001", "f002"],
        action_evidence={a: ["f001", "f002"] for a in ["opening_door", "exiting_doorway"]},
    )
    frames = [frame(1, 0), frame(2, 100), frame(3, 200)]
    if invalid == "still":
        frames[1] = frame(2, 0)
    if invalid == "missing":
        entity.pop("action_evidence")
    if invalid == "reversed":
        entity["action_evidence"] = {a: ["f002", "f001"] for a in entity["actions"]}
    if invalid == "outside":
        entity["action_evidence"] = {a: ["f002", "f003"] for a in entity["actions"]}
    if invalid == "vehicle":
        entity["category"], entity["subtype"] = "vehicle", "car"
    validated, summary = validate_observation(json.dumps(data), frames)
    if invalid is None:
        assert summary == "A person opens the door and exits through the doorway."
    else:
        assert "door" not in summary
        assert validated["entities"][0]["actions"] == ["visible"]
        assert not validated["entities"][0].get("action_evidence")


def test_change_selection_keeps_brief_transition_before_after_and_clip_boundaries():
    from porchlight.ai.frames import select_change_frames

    candidates = [
        (i * 100, bytes([v]) * 24) for i, v in enumerate([0, 1, 2, 3, 100, 4, 5, 6, 7, 8, 9])
    ]
    selected = select_change_frames(candidates, 6)
    assert len(selected) == 6 and selected == sorted(selected)
    assert {0, 3, 4, 5, 10} <= set(selected)


def test_identical_action_tags_are_canonicalized_without_accepting_unknown_actions() -> None:
    data = observation()
    entity = data["entities"][0]
    entity["evidence_frame_ids"] = ["f001", "f002"]
    entity["actions"] = ["passing", "passing"]
    validated, summary = validate_observation(json.dumps(data), [frame(1, 0), frame(2, 100)])
    assert validated["entities"][0]["actions"] == ["passing"]
    assert summary == "A white car passes from left to right."
    entity["actions"] = ["passing", "identify_person", "identify_person"]
    with pytest.raises(ApiError) as error:
        validate_observation(json.dumps(data), [frame(1, 0), frame(2, 100)])
    assert error.value.code == "ANALYSIS_INVALID"


@pytest.mark.parametrize(
    "kind", ["unknown_frame", "reversed_frames", "duplicate_entity", "subtype", "extra_field"]
)
def test_invalid_evidence_and_response_contracts_fail(kind: str) -> None:
    data = observation()
    if kind == "unknown_frame":
        data["entities"][0]["evidence_frame_ids"] = ["f099"]
    elif kind == "reversed_frames":
        data["entities"][0]["evidence_frame_ids"] = ["f002", "f001"]
    elif kind == "duplicate_entity":
        data["entities"].append(copy.deepcopy(data["entities"][0]))
    elif kind == "subtype":
        data["entities"][0]["category"] = "person"
    else:
        data["tools"] = [{"execute": "untrusted"}]
    with pytest.raises(ApiError) as error:
        validate_observation(json.dumps(data), [frame(1, 0), frame(2, 100)])
    assert error.value.code == "ANALYSIS_INVALID"


def transport(state: dict[str, Any], calls: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        route = request.url.path
        calls.append(route)
        if route == "/api/status":
            return httpx.Response(200, json={"cloud": {"disabled": state.get("disabled", True)}})
        if route == "/api/version":
            return httpx.Response(200, json={"version": "synthetic"})
        if route == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": MODEL.name,
                            "digest": state.get("digest", MODEL.digest),
                            "size": 100,
                        }
                    ]
                },
            )
        if route == "/api/show":
            return httpx.Response(
                200,
                json={
                    "capabilities": ["vision"],
                    "details": {"format": "gguf"},
                    "remote_host": "cloud.example" if state.get("remote") else None,
                },
            )
        assert route == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False and "tools" not in body
        assert "camera" not in body and "account" not in body
        if "left" in body["format"]["properties"]:
            result = '{"left":"red","right":"blue"}'
        else:
            state["last_options"] = body["options"]
            assert len(body["messages"]) == 2
            assert body["messages"][1]["images"]
            result = state.get("output", json.dumps(observation()))
        return httpx.Response(200, json={"message": {"content": result}})

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("disabled", [False, None, "true", 1])
def test_private_inference_fails_closed_when_cloud_policy_is_not_verified(
    config: Config,
    disabled: Any,
) -> None:
    calls: list[str] = []

    async def run() -> None:
        ollama = Ollama(config, transport({"disabled": disabled}, calls))
        try:
            with pytest.raises(ApiError) as error:
                await ollama.analyze(MODEL, [frame(1, 0)])
            assert error.value.code == "LOCAL_ONLY_REQUIRED"
            assert "/api/chat" not in calls
        finally:
            await ollama.close()

    asyncio.run(run())


def make_pipeline(
    config: Config, video: bytes, state: dict[str, Any], media_type: str = "video/mp4"
) -> tuple[Database, AnalysisPipeline, str, list[str]]:
    db = Database(config.data_root)
    db.migrate()
    with db.session() as session:
        session.add(
            SettingsRow(
                id=1,
                revision=1,
                values=AppSettings(revision=1, ai_enabled=True, ai_model=MODEL.name).model_dump(
                    exclude={"revision"}
                ),
            )
        )
        session.add(
            IntegrationState(id="ai_control", values={"enabled_at": datetime.now(UTC).isoformat()})
        )
        session.commit()
    importer = Importer(config, db)
    sha = hashlib.sha256(video).hexdigest()
    (importer.media / f"{sha}{'.jpg' if media_type == 'image/jpeg' else '.mp4'}").write_bytes(video)
    event_id = importer.commit_import(
        {
            "sha256": sha,
            "source_key": "synthetic:new",
            "bytes": len(video),
            "captured_at": datetime.now(UTC).isoformat(),
            "discovered_at": datetime.now(UTC).isoformat(),
            "source_type": "blink_cloud",
            "duration_seconds": 0 if media_type == "image/jpeg" else 1,
            "media_type": media_type,
            "width": 320,
            "height": 240,
        }
    )
    calls: list[str] = []
    pipeline = AnalysisPipeline(config, db, Ollama(config, transport(state, calls)))
    pipeline.record_test(
        ModelTestResult(
            passed=True,
            model=MODEL.name,
            digest=MODEL.digest,
            elapsed_seconds=0,
            message="Synthetic test",
        )
    )
    return db, pipeline, event_id, calls


@pytest.mark.parametrize("source_type", ["blink_cloud", "blink_local"])
@pytest.mark.parametrize("enabled", [True, False])
def test_archived_clip_signals_ai_immediately_even_while_inference_is_busy(
    config: Config,
    synthetic_mp4: bytes,
    monkeypatch: pytest.MonkeyPatch,
    source_type: str,
    enabled: bool,
) -> None:
    db, pipeline, _, _ = make_pipeline(config, synthetic_mp4, {})
    with db.session() as session:
        settings = session.get(SettingsRow, 1)
        assert settings
        settings.values = {**settings.values, "ai_enabled": enabled}
        session.commit()

    async def run() -> None:
        busy, scanned = asyncio.Event(), asyncio.Event()
        original_scan = pipeline.schedule_new

        async def scan() -> None:
            await original_scan()
            scanned.set()

        async def hold_inference(job: Job) -> None:
            busy.set()
            await asyncio.Event().wait()

        async def download(path: str, destination: Any) -> None:
            destination.write_bytes(synthetic_mp4)

        monkeypatch.setattr(pipeline, "schedule_new", scan)
        monkeypatch.setattr(pipeline, "execute", hold_inference)
        provider = SimpleNamespace(
            recording_source_id="synthetic-source", download_recording=download
        )
        service = Recordings(
            config,
            db,
            provider,
            Importer(config, db),
            source_type,
            on_archived=pipeline.notify_recording,
        )
        service.control(True)
        worker = asyncio.create_task(pipeline.run())
        try:
            await asyncio.wait_for(scanned.wait(), 2)
            if enabled:
                await asyncio.wait_for(busy.wait(), 2)
            scanned.clear()
            now = datetime.now(UTC).isoformat()
            key = f"{source_type}:synthetic-arrival"
            service.persist_page(
                provider.recording_source_id,
                RecordingPage(
                    [
                        ClipReference(
                            key, "synthetic-camera", now, now, "/api/media/synthetic.mp4", False
                        ),
                    ],
                    True,
                ),
            )
            with db.session() as session:
                reference = session.scalar(
                    select(RecordingReference).where(RecordingReference.source_key == key)
                )
                assert reference
                reference_id = reference.id
            await service.download(reference_id)
            # A fresh scan happens via the archive signal, without a 30-second poll
            # or waiting for the held inference to complete.
            await asyncio.wait_for(scanned.wait(), 2)
            with db.session() as session:
                reference = session.get(RecordingReference, reference_id)
                assert reference and reference.state == "archived"
                event = session.get(Event, reference.event_id)
                assert event
                asset = session.get(MediaAsset, event.media_id)
                assert (
                    asset and (config.data_root / asset.relative_path).read_bytes() == synthetic_mp4
                )
                job = session.scalar(
                    select(Job).where(
                        Job.type == "ai_analyze", Job.payload["event_id"].as_string() == event.id
                    )
                )
                if enabled:
                    assert job and job.status == "queued" and job.payload["automatic"] is True
                    assert event.analysis_status == "queued" and busy.is_set()
                else:
                    assert job is None and event.analysis_status == "not_analyzed"
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
            await pipeline.ollama.close()
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_jpeg_analysis_uses_one_image_and_suppresses_direction(
    config: Config, synthetic_jpeg: bytes
) -> None:
    db, pipeline, event_id, calls = make_pipeline(config, synthetic_jpeg, {}, "image/jpeg")

    async def run() -> None:
        queued = pipeline.enqueue(event_id, MODEL, automatic=False)
        job = pipeline.claim()
        assert job and job.id == queued.job_id
        await pipeline.execute(job)
        with db.session() as session:
            analysis = session.scalar(select(Analysis).where(Analysis.event_id == event_id))
            assert analysis and len(analysis.frames) == 1
            assert analysis.observation["observation_mode"] == "single_image"
            entity = analysis.observation["entities"][0]
            assert entity["direction"] == "unknown" and entity["actions"] == ["visible"]
        assert "/api/chat" in calls
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_actual_extraction_deduplicates_still_clip(config: Config, synthetic_mp4: bytes) -> None:
    media = config.data_root / "media"
    media.mkdir(parents=True)
    path = media / "synthetic.mp4"
    path.write_bytes(synthetic_mp4)
    frames = asyncio.run(extract_frames(path, 1, config))
    assert len(frames) == 1 and frames[0].id == "f001"
    assert frames[0].image.startswith(b"\xff\xd8")
    assert frames[0].monochrome is False


@pytest.mark.parametrize("workload, expected", [("light", 3), ("balanced", 6)])
def test_workloads_sample_motion_with_native_decoder(
    config: Config, workload: Workload, expected: int
) -> None:
    executable = config.tool_path("ffmpeg")
    assert executable
    media = config.data_root / "media"
    media.mkdir(parents=True)
    path = media / "generated-motion.mp4"

    async def run() -> None:
        await run_tool(
            executable,
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=2:size=320x240:rate=10",
            "-c:v",
            "mpeg4",
            str(path),
        )
        frames = await extract_frames(path, 2, config, workload=workload)
        assert len(frames) == expected
        assert frames[0].offset_ms == 0 and frames[-1].offset_ms == 1880
        assert all(frame.evidence()["workload"] == workload for frame in frames)

    asyncio.run(run())


def test_queued_workload_is_frozen_and_new_preset_produces_new_revision(
    config: Config,
    synthetic_mp4: bytes,
) -> None:
    state: dict[str, Any] = {}
    db, pipeline, event_id, _ = make_pipeline(config, synthetic_mp4, state)
    with db.session() as session:
        row = session.get(SettingsRow, 1)
        row.values = {**row.values, "ai_workload": "light"}
        session.commit()
    light = pipeline.enqueue(event_id, MODEL, automatic=False)
    with db.session() as session:
        row = session.get(SettingsRow, 1)
        row.values = {**row.values, "ai_workload": "balanced"}
        session.commit()
    assert pipeline.enqueue(event_id, MODEL, automatic=False).job_id == light.job_id

    async def run() -> None:
        job = pipeline.claim()
        assert job and job.id == light.job_id and job.payload["workload"] == "light"
        await pipeline.execute(job)
        assert state["last_options"]["num_ctx"] == 4096
        assert pipeline.latest(event_id).workload == "light"
        balanced = pipeline.enqueue(event_id, MODEL, automatic=False)
        assert balanced.job_id != light.job_id
        job = pipeline.claim()
        assert job
        await pipeline.execute(job)
        assert state["last_options"]["num_ctx"] == 8192
        assert pipeline.latest(event_id).workload == "balanced"
        with db.session() as session:
            revisions = list(session.scalars(select(Analysis).order_by(Analysis.revision)))
            assert len(revisions) == 2
            assert revisions[0].input_fingerprint != revisions[1].input_fingerprint
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


@pytest.mark.parametrize("changed", ["contract", "extraction_version", "workload_version", "key"])
def test_old_queued_contract_never_sends_media_and_preserves_accepted_revision(
    config: Config, synthetic_mp4: bytes, changed: str
) -> None:
    db, pipeline, event_id, calls = make_pipeline(config, synthetic_mp4, {})

    async def run() -> None:
        pipeline.enqueue(event_id, MODEL, automatic=False)
        first = pipeline.claim()
        assert first
        await pipeline.execute(first)
        original = pipeline.latest(event_id)
        assert original and original.revision == 1
        queued = pipeline.enqueue(event_id, MODEL, automatic=False, reanalyze=True)
        with db.session() as session:
            row = session.get(Job, queued.job_id)
            assert row
            if changed == "key":
                row.dedup_key = row.dedup_key.replace(row.payload["contract"], "old-prompt")
                row.payload = {
                    key: value
                    for key, value in row.payload.items()
                    if key not in {"contract", "extraction_version", "workload_version"}
                }
            else:
                row.payload = {**row.payload, changed: "old-version"}
            session.commit()
        calls.clear()
        job = pipeline.claim()
        assert job and job.id == queued.job_id
        await pipeline.execute(job)
        assert "/api/chat" not in calls
        with db.session() as session:
            row = session.get(Job, queued.job_id)
            assert row and row.status == "blocked"
            assert row.safe_error == "ANALYSIS_CONTRACT_CHANGED" and row.lease_until is None
            assert session.get(Event, event_id).media_id
        assert pipeline.latest(event_id) == original
        pipeline.enqueue(event_id, MODEL, automatic=False, reanalyze=True)
        current = pipeline.claim()
        assert current
        await pipeline.execute(current)
        assert "/api/chat" in calls and pipeline.latest(event_id).revision == 2
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_current_legacy_job_without_explicit_version_fields_remains_runnable(
    config: Config, synthetic_mp4: bytes
) -> None:
    db, pipeline, event_id, calls = make_pipeline(config, synthetic_mp4, {})
    queued = pipeline.enqueue(event_id, MODEL, automatic=False)
    with db.session() as session:
        row = session.get(Job, queued.job_id)
        row.payload = {
            key: value
            for key, value in row.payload.items()
            if key not in {"contract", "extraction_version", "workload_version"}
        }
        session.commit()

    async def run() -> None:
        job = pipeline.claim()
        assert job
        await pipeline.execute(job)
        assert "/api/chat" in calls and pipeline.latest(event_id).revision == 1
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_historical_provenance_blocks_auto_ai_but_keeps_manual_review(
    config: Config,
    synthetic_mp4: bytes,
) -> None:
    db, pipeline, event_id, calls = make_pipeline(config, synthetic_mp4, {})
    with db.session() as session:
        event = session.get(Event, event_id)
        assert event
        event.historical = True
        session.commit()

    async def run() -> None:
        await pipeline.schedule_new()
        assert pipeline.claim() is None
        with pytest.raises(ApiError) as error:
            pipeline.enqueue(event_id, MODEL, automatic=True)
        assert error.value.code == "AI_HISTORY_MANUAL_REQUIRED"
        requested = pipeline.enqueue(event_id, MODEL, automatic=False)
        job = pipeline.claim()
        assert job and job.id == requested.job_id
        await pipeline.execute(job)
        with db.session() as session:
            event = session.get(Event, event_id)
            assert event and event.historical and event.analysis_status == "analyzed"
        assert "/api/chat" in calls
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_durable_analysis_restart_replay_preserves_annotations_and_avoids_backfill(
    config: Config,
    synthetic_mp4: bytes,
) -> None:
    db, pipeline, event_id, _ = make_pipeline(config, synthetic_mp4, {})
    with db.session() as session:
        event = session.get(Event, event_id)
        assert event
        event.favourite, event.note = True, "Preserve this annotation"
        session.commit()

    async def run() -> None:
        await pipeline.schedule_new()
        job = pipeline.claim()
        assert job
        assert pipeline.enqueue(event_id, MODEL, automatic=False).job_id == job.id
        # Simulate an interrupted inference and restart with the same persisted profile.
        recovered = AnalysisPipeline(config, db, pipeline.ollama)
        with db.session() as session:
            event = session.get(Event, event_id)
            assert event and event.analysis_status == "queued"
        resumed = recovered.claim()
        assert resumed and resumed.id == job.id and resumed.attempt == 2
        await recovered.execute(resumed)
        with db.session() as session:
            persisted = session.get(Job, job.id)
            assert persisted
            persisted.status = "running"  # Crash after accepted result, before completion marker.
            session.commit()
        AnalysisPipeline(config, db, pipeline.ollama)
        with db.session() as session:
            persisted = session.get(Job, job.id)
            assert persisted and persisted.status == "done"
        await recovered.execute(resumed)  # Replayed completion cannot duplicate the result.
        with db.session() as session:
            event = session.get(Event, event_id)
            assert event and event.analysis_status == "analyzed"
            assert event.favourite and event.note == "Preserve this annotation"
            assert session.scalar(select(func.count()).select_from(Analysis)) == 1
            event.analysis_status, event.captured_at = "not_analyzed", "2020-01-01T00:00:00+00:00"
            session.commit()
        await pipeline.schedule_new()
        assert pipeline.claim() is None
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


@pytest.mark.parametrize("clock_shift", [-3600, 3600])
def test_analysis_restart_after_clock_change_recovers_a_claimed_manual_job(
    config: Config,
    synthetic_mp4: bytes,
    monkeypatch: pytest.MonkeyPatch,
    clock_shift: int,
) -> None:
    db, pipeline, event_id, calls = make_pipeline(config, synthetic_mp4, {})
    try:
        requested = pipeline.enqueue(event_id, MODEL, automatic=False)
        claimed = pipeline.claim()
        assert claimed is not None and claimed.id == requested.job_id
        changed_now = time.time() + clock_shift
        monkeypatch.setattr(
            "porchlight.ai.pipeline.time", SimpleNamespace(time=lambda: changed_now)
        )
        recovered = AnalysisPipeline(config, db, pipeline.ollama)
        resumed = recovered.claim()
        assert resumed is not None and resumed.id == claimed.id
        assert resumed.attempt == claimed.attempt + 1
        assert recovered.claim() is None
        with db.session() as session:
            event = session.get(Event, event_id)
            assert event is not None and event.analysis_status == "analyzing"
            assert event.source_type == "blink_cloud"
            assert session.scalar(select(func.count()).select_from(Analysis)) == 0
        assert "/api/chat" not in calls
    finally:
        asyncio.run(pipeline.ollama.close())
        db.close()


def test_policy_revocation_and_malformed_results_keep_recordings_playable(
    config: Config,
    synthetic_mp4: bytes,
) -> None:
    state: dict[str, Any] = {"disabled": False}
    db, pipeline, event_id, calls = make_pipeline(config, synthetic_mp4, state)
    pipeline.enqueue(event_id, MODEL, automatic=False)

    async def run() -> None:
        job = pipeline.claim()
        assert job
        await pipeline.execute(job)
        assert "/api/chat" not in calls
        state.update(disabled=True, output="invalid output containing SECRET")
        pipeline.enqueue(event_id, MODEL, automatic=False)
        job = pipeline.claim()
        assert job
        await pipeline.execute(job)
        with db.session() as session:
            row = session.get(Job, job.id)
            assert row and row.status == "queued"
            row.available_at = 0
            session.commit()
        retry = pipeline.claim()
        assert retry
        await pipeline.execute(retry)
        with db.session() as session:
            row = session.get(Job, job.id)
            event = session.get(Event, event_id)
            assert row and row.status == "failed" and row.attempt == 2
            assert row.safe_error == "ANALYSIS_INVALID"
            assert event and event.analysis_status == "analysis_failed" and event.media_id
            assert session.scalar(select(func.count()).select_from(Analysis)) == 0
        assert pipeline.claim() is None
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_authenticated_api_to_worker_to_summary_search_and_range_playback(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
) -> None:
    client, headers = authenticated
    calls: list[str] = []
    ollama = client.app.state.ollama
    ollama.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:11434",
        transport=transport({}, calls),
        trust_env=False,
    )
    event = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    ).json()
    route = f"/api/v1/events/{event['id']}"
    assert client.post(route + "/analyze", json={}).status_code == 403
    assert client.post(route + "/analyze", headers=headers, json={}).status_code == 409
    assert client.post("/api/v1/ollama/test", headers=headers, json={"model": MODEL.name}).json()[
        "passed"
    ]
    settings = client.get("/api/v1/settings").json()
    assert (
        client.put(
            "/api/v1/settings",
            headers=headers,
            json={
                **settings,
                "ai_model": MODEL.name,
                "ai_enabled": False,
            },
        ).status_code
        == 200
    )
    assert client.get(route + "/analysis").json() is None  # Existing history was not auto-queued.
    assert client.post(route + "/analyze", headers=headers, json={}).status_code == 202
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        current = client.get(route).json()
        if current["analysis_status"] == "analyzed":
            break
        time.sleep(0.05)
    assert current["analysis_status"] == "analyzed"
    assert not client.get("/api/v1/settings").json()["ai_enabled"]
    assert current["summary"] == "A white car is visible."  # Synthetic model fixture, not accuracy.
    assert current["object_categories"] == ["vehicle"]
    detail = client.get(route + "/analysis").json()
    assert detail["frame_count"] == 1
    assert detail["evidence_frames"] == [{"frame_id": "f001", "offset_ms": 0}]
    sample_route = route + "/analysis/1/frames/f001"
    sample = client.get(sample_route)
    assert sample.status_code == 200 and sample.headers["cache-control"] == "no-store"
    assert sample.headers["content-type"] == "image/jpeg"
    with client.app.state.db.session() as session:
        accepted = session.scalar(select(Analysis).where(Analysis.event_id == event["id"]))
        assert hashlib.sha256(sample.content).hexdigest() == accepted.frames[0]["sha256"]
        accepted.frames = [{**accepted.frames[0], "sha256": "0" * 64}]
        session.commit()
    assert client.get(sample_route).json()["code"] == "EVIDENCE_CHANGED"
    assert client.get(route + "/analysis/1/frames/f099").status_code == 404
    assert client.get(route + "/analysis/999/frames/f001").status_code == 404
    assert client.get(route + "/analysis/0/frames/f001").status_code == 422
    assert client.get(sample_route, headers={"Origin": "https://bad.invalid"}).status_code == 403
    client.app.state.evidence.pending = 12
    assert client.get(sample_route).status_code == 429
    client.app.state.evidence.pending = 0
    matches = client.get("/api/v1/events?query=white%20car").json()["items"]
    assert len(matches) == 1 and matches[0]["object_categories"] == ["vehicle"]
    assert (
        client.get(
            f"/api/v1/media/{event['media_id']}", headers={"Range": "bytes=0-15"}
        ).status_code
        == 206
    )
    client.cookies.clear()
    assert client.get(sample_route).status_code == 401


def test_paused_automatic_queue_allows_explicit_manual_request(
    config: Config, synthetic_mp4: bytes
) -> None:
    db, pipeline, event_id, _ = make_pipeline(config, synthetic_mp4, {})
    pipeline.enqueue(event_id, MODEL, automatic=True)
    with db.session() as session:
        row = session.get(SettingsRow, 1)
        assert row
        row.values = {**row.values, "ai_enabled": False}
        session.commit()
    assert pipeline.claim() is None

    async def run() -> None:
        requested = await pipeline.request(event_id, False)
        job = pipeline.claim()
        assert job and job.id == requested.job_id and not job.payload["automatic"]
        await pipeline.execute(job)
        assert not pipeline.settings().ai_enabled
        with db.session() as session:
            assert session.get(Event, event_id).analysis_status == "analyzed"
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_failed_reanalysis_retries_latest_job_not_previous_success(
    config: Config, synthetic_mp4: bytes
) -> None:
    state: dict[str, Any] = {}
    db, pipeline, event_id, _ = make_pipeline(config, synthetic_mp4, state)

    async def run() -> None:
        pipeline.enqueue(event_id, MODEL, automatic=False)
        first = pipeline.claim()
        assert first
        await pipeline.execute(first)
        second = pipeline.enqueue(event_id, MODEL, automatic=False, reanalyze=True)
        job = pipeline.claim()
        assert job and job.id == second.job_id and job.id != first.id
        state["disabled"] = False
        await pipeline.execute(job)
        retry = pipeline.enqueue(event_id, MODEL, automatic=False)
        assert retry.job_id == second.job_id
        state["disabled"] = True
        job = pipeline.claim()
        assert job
        await pipeline.execute(job)
        with db.session() as session:
            assert session.scalar(select(func.count()).select_from(Analysis)) == 2
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_altered_media_is_not_sent_to_model(config: Config, synthetic_mp4: bytes) -> None:
    db, pipeline, event_id, calls = make_pipeline(config, synthetic_mp4, {})
    asset = next((config.data_root / "media").glob("*.mp4"))
    asset.write_bytes(b"altered file")
    pipeline.enqueue(event_id, MODEL, automatic=False)

    async def run() -> None:
        job = pipeline.claim()
        assert job
        await pipeline.execute(job)
        with db.session() as session:
            row = session.get(Job, job.id)
            assert row and row.safe_error == "MEDIA_CHANGED"
        assert "/api/chat" not in calls
        await pipeline.ollama.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_fresh_automatic_recording_has_priority_over_requested_history(
    config: Config, synthetic_mp4: bytes
) -> None:
    db, pipeline, event_id, _ = make_pipeline(config, synthetic_mp4, {})
    try:
        with db.session() as session:
            original = session.get(Event, event_id)
            assert original
            original.captured_at = "2020-01-01T00:00:00+00:00"
            session.add(
                Event(
                    id="synthetic-fresh",
                    source_type="blink_cloud",
                    source_key="synthetic:fresh-priority",
                    captured_at=datetime.now(UTC).isoformat(),
                    discovered_at=datetime.now(UTC).isoformat(),
                    timestamp_quality="provider",
                    media_id=original.media_id,
                    analysis_status="not_analyzed",
                    summary=None,
                    favourite=False,
                    note="",
                    camera_id=None,
                )
            )
            session.commit()
        fresh = pipeline.enqueue("synthetic-fresh", MODEL, automatic=True)
        historical = pipeline.enqueue(event_id, MODEL, automatic=False)
        claimed = pipeline.claim()
        assert claimed and claimed.id == fresh.job_id
        with db.session() as session:
            waiting = session.get(Job, historical.job_id)
            assert waiting and waiting.status == "queued"
    finally:
        asyncio.run(pipeline.ollama.close())
        db.close()
