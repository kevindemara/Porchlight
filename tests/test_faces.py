import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError
from porchlight.catalog import Archive
from porchlight.config import Config
from porchlight.faces.contracts import (
    FaceBox,
    FaceEnrollmentBatch,
    FaceFrame,
    FaceReport,
    FaceSelection,
)
from porchlight.faces.detector import MANIFEST, Detector, check_runtime, sample_offsets
from porchlight.faces.pipeline import FacePipeline, preserve_manual_labels
from porchlight.storage.database import Database
from porchlight.storage.models import Event, FaceDetection, Job, MediaAsset
from pydantic import ValidationError
from sqlalchemy import func, select


def store(db: Database, config: Config, content: bytes = b"synthetic", **overrides: object) -> str:
    event_id, asset_id = str(uuid4()), str(uuid4())
    folder = config.data_root / "media"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"media/{asset_id}.mp4"
    (config.data_root / name).write_bytes(content)
    with db.session() as session:
        session.add(
            MediaAsset(
                id=asset_id,
                sha256=hashlib.sha256(content + asset_id.encode()).hexdigest(),
                relative_path=name,
                bytes=len(content),
                duration_seconds=1,
                width=320,
                height=240,
                media_type="video/mp4",
            )
        )
        session.flush()
        now = datetime.now(UTC).isoformat()
        values = dict(
            id=event_id,
            source_type="manual_import",
            source_key=event_id,
            captured_at=now,
            discovered_at=now,
            timestamp_quality="manual",
            media_id=asset_id,
            analysis_status="not_analyzed",
            summary=None,
            favourite=False,
            note="",
        )
        session.add(Event(**{**values, **overrides}))
        session.commit()
    return event_id


@pytest.fixture
def pipeline(config: Config, monkeypatch: pytest.MonkeyPatch):
    db = Database(config.data_root)
    db.migrate()
    worker = FacePipeline(config, db)
    monkeypatch.setattr(worker, "ready", lambda: None)
    yield worker
    db.close()


def report(face: bool = True) -> FaceReport:
    box = FaceBox(x=10, y=15, width=30, height=40, score=0.95, small=True, low_sharpness=True)
    return FaceReport(
        frames=[
            FaceFrame(
                offset_ms=0, sha256="a" * 64, width=320, height=240, faces=[box] if face else []
            )
        ]
    )


def test_sampling_is_bounded_chronological_and_end_safe():
    assert sample_offsets(0.3) == [0, 180]
    assert sample_offsets(10)[-1] == 9880
    ten_seconds = sample_offsets(10)
    assert len(ten_seconds) == 40
    assert max(
        right - left for left, right in zip(ten_seconds, ten_seconds[1:], strict=False)
    ) <= 300
    assert any(5050 <= offset <= 5300 for offset in ten_seconds)
    assert len(sample_offsets(300)) == 48
    assert sample_offsets(0, image=True) == [0]
    for invalid in (0, -1, 301, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            sample_offsets(invalid)


def test_report_rejects_identity_geometry_and_bad_evidence():
    assert FaceBox(x=1, y=1, width=10, height=10, score=0.8, small=True, low_sharpness=False)
    with pytest.raises(ValidationError):
        FaceBox(x=1, y=1, width=10, height=10, score=0.79, small=True, low_sharpness=False)
    valid = report().model_dump()
    for key in ("name", "embedding", "age", "gender"):
        face = {**valid["frames"][0]["faces"][0], key: "synthetic"}
        with pytest.raises(ValidationError):
            FaceBox.model_validate(face)
    invalid = report().model_dump()
    invalid["frames"][0]["faces"][0]["width"] = 320
    with pytest.raises(ValidationError):
        FaceReport.model_validate(invalid)
    invalid = report().model_dump()
    invalid["frames"] *= 2
    with pytest.raises(ValidationError):
        FaceReport.model_validate(invalid)


def test_rescan_keeps_owner_label_only_on_same_verified_face() -> None:
    owner_id, other_id = uuid4(), uuid4()
    previous = report()
    previous.frames[0].faces[0].profile_id = owner_id
    updated = report()
    updated.frames[0].faces[0].profile_id = other_id
    updated.frames[0].faces[0].match_score = 0.8
    preserved = preserve_manual_labels(previous, updated)
    assert preserved.frames[0].faces[0].profile_id == owner_id
    assert preserved.frames[0].faces[0].match_score is None
    changed = report()
    changed.frames[0].sha256 = "b" * 64
    assert preserve_manual_labels(previous, changed).frames[0].faces[0].profile_id is None


def test_model_digest_mismatch_is_gated(config: Config, tmp_path: Path):
    if not config.face_model.is_file():
        pytest.skip("Optional detector not installed")
    bad_model = tmp_path / "model.onnx"
    bad_model.write_bytes(b"x" * MANIFEST["bytes"])
    with pytest.raises(ApiError) as exc:
        check_runtime(bad_model)
    assert exc.value.code == "FACE_MODEL_MISMATCH"


def test_changed_policy_fails_without_inference(
    pipeline: FacePipeline, monkeypatch: pytest.MonkeyPatch
):
    event_id = store(pipeline.db, pipeline.config)
    pipeline.enqueue(event_id)
    job = pipeline.claim()
    assert job
    with pipeline.db.session() as session:
        current = session.get(Job, job.id)
        current.payload = {**current.payload, "policy": "old-policy"}
        session.commit()
        job = current

    async def should_not_run(_: str):
        pytest.fail("Incompatible policy must not decode private media")

    monkeypatch.setattr(pipeline, "detect", should_not_run)
    asyncio.run(pipeline.execute(job))
    assert pipeline.result(event_id).status == "failed"


def test_queue_bound_keeps_all_raw_events(pipeline: FacePipeline):
    for _ in range(30):
        pipeline.enqueue(store(pipeline.db, pipeline.config))
    extra = store(pipeline.db, pipeline.config)
    with pytest.raises(ApiError) as exc:
        pipeline.enqueue(extra)
    assert exc.value.code == "FACE_QUEUE_FULL"
    assert pipeline.view().queued == 30
    assert pipeline.result(extra).status == "not_requested"
    with pipeline.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 31


def test_native_detector_has_no_faces_in_synthetic_color(config: Config, synthetic_jpeg: bytes):
    if not config.face_model.is_file():
        pytest.skip(
            "Optional detector model not installed; installation requires explicit approval"
        )
    detector = Detector(config.face_model)
    found = detector.detect(synthetic_jpeg, 0)
    assert found.faces == []
    assert found.sha256 == hashlib.sha256(synthetic_jpeg).hexdigest()
    with pytest.raises(ValueError):
        detector.detect(b"invalid jpeg", 0)


def test_queue_dedup_restart_and_previous_result_survives_failure(
    pipeline: FacePipeline, monkeypatch: pytest.MonkeyPatch
):
    event_id = store(pipeline.db, pipeline.config)
    pipeline.enqueue(event_id)
    pipeline.enqueue(event_id)
    assert pipeline.view().queued == 1
    claimed = pipeline.claim()
    assert claimed
    restarted = FacePipeline(pipeline.config, pipeline.db)
    monkeypatch.setattr(restarted, "ready", lambda: None)
    assert restarted.result(event_id).status == "queued"

    async def success(_: str):
        return report()

    monkeypatch.setattr(restarted, "detect", success)
    claimed = restarted.claim()
    assert claimed
    asyncio.run(restarted.execute(claimed))
    assert restarted.result(event_id).status == "done"
    assert restarted.result(event_id).report == report()
    restarted.enqueue(event_id)
    assert restarted.view().completed == 1 and restarted.view().queued == 0

    async def failure(_: str):
        raise ValueError("SYNTHETIC_PRIVATE_TEXT")

    monkeypatch.setattr(restarted, "detect", failure)
    restarted.enqueue(event_id, reanalyze=True)
    for attempt in range(3):
        with restarted.db.session() as session:
            for job in session.scalars(select(Job).where(Job.status == "queued")):
                job.available_at = 0
            session.commit()
        claimed = restarted.claim()
        assert claimed and claimed.attempt == attempt + 1
        asyncio.run(restarted.execute(claimed))
    result = restarted.result(event_id)
    assert result.status == "failed" and result.report == report()
    assert "SYNTHETIC_PRIVATE_TEXT" not in result.model_dump_json()
    with restarted.db.session() as session:
        assert session.get(Event, event_id).analysis_status == "not_analyzed"
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 1


def test_automatic_only_new_recent_nonhistorical_blink(pipeline: FacePipeline):
    store(pipeline.db, pipeline.config, source_type="blink_cloud")  # Before opt-in.
    pipeline.set_enabled(True)
    eligible = store(pipeline.db, pipeline.config, source_type="blink_cloud")
    store(pipeline.db, pipeline.config, source_type="blink_local", historical=True)
    store(
        pipeline.db,
        pipeline.config,
        source_type="blink_cloud",
        captured_at=(datetime.now(UTC) - timedelta(days=2)).isoformat(),
    )
    store(pipeline.db, pipeline.config)
    pipeline.schedule()
    assert pipeline.result(eligible).status == "queued"
    assert pipeline.view().queued == 1
    pipeline.set_enabled(False)
    assert pipeline.claim() is None
    pipeline.enqueue(eligible)  # Explicit request promotes paused automatic job.
    job = pipeline.claim()
    assert job and not job.payload["automatic"]


def test_automatic_expiry_and_disable_during_detection(
    pipeline: FacePipeline, monkeypatch: pytest.MonkeyPatch
):
    pipeline.set_enabled(True)
    old = store(
        pipeline.db,
        pipeline.config,
        source_type="blink_cloud",
        captured_at=(datetime.now(UTC) - timedelta(days=2)).isoformat(),
    )
    pipeline.enqueue(old, automatic=True)
    assert pipeline.claim() is None
    assert pipeline.result(old).status == "expired"
    fresh = store(pipeline.db, pipeline.config, source_type="blink_local")
    pipeline.enqueue(fresh, automatic=True)
    job = pipeline.claim()
    assert job

    async def detect(_: str):
        pipeline.set_enabled(False)
        return report()

    monkeypatch.setattr(pipeline, "detect", detect)
    asyncio.run(pipeline.execute(job))
    assert pipeline.result(fresh).status == "expired"
    assert pipeline.result(fresh).report is None


def test_delete_protects_running_and_cascades_results(
    pipeline: FacePipeline, monkeypatch: pytest.MonkeyPatch
):
    event_id = store(pipeline.db, pipeline.config)
    pipeline.enqueue(event_id)
    job = pipeline.claim()
    assert job
    archive = Archive(pipeline.config, pipeline.db)
    with pytest.raises(ApiError) as err:
        archive.delete_event(event_id)
    assert err.value.code == "ANALYSIS_BUSY"

    async def detect(_: str):
        return report()

    monkeypatch.setattr(pipeline, "detect", detect)
    asyncio.run(pipeline.execute(job))
    archive.delete_event(event_id)
    with pipeline.db.session() as session:
        assert session.get(FaceDetection, event_id) is None
        assert session.scalar(select(func.count()).select_from(Job)) == 0


def test_native_subprocess_clip_and_no_ai_dependency(pipeline: FacePipeline, synthetic_mp4: bytes):
    if not pipeline.config.face_model.is_file():
        pytest.skip("Optional detector model not installed")
    event_id = store(pipeline.db, pipeline.config, synthetic_mp4)
    pipeline.enqueue(event_id)
    job = pipeline.claim()
    assert job
    asyncio.run(pipeline.execute(job))
    result = pipeline.result(event_id)
    assert result.status == "done"
    assert len(result.report.frames) == 4
    assert result.report.frames[0].faces == []


def test_routes_require_session_and_csrf(client: TestClient):
    assert client.get("/api/v1/face-detection/status").status_code == 401
    assert client.get(f"/api/v1/events/{uuid4()}/faces").status_code == 401
    assert client.get("/api/v1/face-detection/gallery").status_code == 401
    assert client.post("/api/v1/face-detection/rescan-recent").status_code == 403
    assert client.post("/api/v1/face-detection/people/batch").status_code == 403
    assert client.post("/api/v1/face-detection/suggestions/approve").status_code == 403
    assert (
        client.put("/api/v1/face-detection/auto-enroll", json={"enabled": True}).status_code
        == 403
    )
    assert client.get(f"/api/v1/events/{uuid4()}/faces/thumbnails/0/0").status_code == 401


def test_recent_rescan_queues_at_most_twenty_videos(pipeline: FacePipeline):
    for _ in range(23):
        store(pipeline.db, pipeline.config)
    result = pipeline.rescan_recent()
    assert result.requested == result.queued == 20
    assert result.already_running == 0
    assert pipeline.view().queued == 20


def test_authenticated_gallery_groups_recent_synthetic_faces(authenticated, config: Config,
                                                               monkeypatch: pytest.MonkeyPatch):
    client, _ = authenticated
    events = [store(client.app.state.db, config) for _ in range(2)]
    with client.app.state.db.session() as session:
        for event_index, event_id in enumerate(events):
            face = FaceBox(
                x=20, y=20, width=80, height=80, score=0.91,
                small=False, low_sharpness=False,
            )
            sample = FaceReport(frames=[FaceFrame(
                offset_ms=offset * 100, sha256="a" * 64, width=320, height=240, faces=[face],
            ) for offset in range(6 if event_index == 0 else 1)])
            session.add(FaceDetection(
                event_id=event_id, job_id=str(uuid4()),
                report=sample.model_dump(mode="json"),
                created_at=datetime.now(UTC).isoformat(), elapsed_seconds=0.1,
            ))
        session.commit()

    async def fake_frame(_event_id: str, _offset_ms: int) -> bytes:
        return b"generated-sample"

    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    monkeypatch.setattr(client.app.state.faces, "sample_frame", fake_frame)
    monkeypatch.setattr("porchlight.faces.pipeline.feature_for_box", lambda *_: feature)
    response = client.get("/api/v1/face-detection/gallery")
    assert response.status_code == 200
    gallery = response.json()
    assert gallery["recordings_reviewed"] == 2
    assert gallery["total_recordings"] == 2
    assert gallery["next_offset"] is None
    assert len(gallery["groups"]) == 1
    assert gallery["groups"][0]["sightings"] == 7
    assert len(gallery["groups"][0]["samples"]) == 3
    assert gallery["omitted_faces"] == 0


def test_gallery_pages_all_reports_by_capture_time(authenticated, config: Config):
    client, _ = authenticated
    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    person = client.app.state.faces.people.create_samples("Known person", [feature])
    older_person = client.app.state.faces.people.create_samples("Older person", [feature])
    event_ids = [
        store(
            client.app.state.db, config,
            captured_at=(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)).isoformat(),
        )
        for index in range(22)
    ]
    with client.app.state.db.session() as session:
        for index, event_id in enumerate(event_ids):
            saved_report = report()
            saved_report.frames[0].faces[0] = saved_report.frames[0].faces[0].model_copy(
                update={
                    "profile_id": older_person.id if index == 0 else person.id,
                    "match_score": 0.9 if index == 1 else None,
                }
            )
            session.add(FaceDetection(
                event_id=event_id, job_id=str(uuid4()),
                report=saved_report.model_dump(mode="json"),
                # Scan completion order should not determine gallery order.
                created_at=(datetime(2026, 2, 1, tzinfo=UTC) - timedelta(days=index)).isoformat(),
                elapsed_seconds=0.1,
            ))
        session.commit()

    first = client.get("/api/v1/face-detection/gallery").json()
    older = client.get("/api/v1/face-detection/gallery?offset=20").json()
    assert first["total_recordings"] == older["total_recordings"] == 22
    assert first["labeled_totals"][str(person.id)] == 21
    assert older["labeled_totals"][str(person.id)] == 21
    assert first["confirmed_totals"][str(person.id)] == 20
    assert older["confirmed_totals"][str(person.id)] == 20
    assert first["labeled_totals"][str(older_person.id)] == 1
    assert {row["person_id"] for row in first["saved_people"]} == {
        str(person.id), str(older_person.id),
    }
    assert len(first["saved_people"][0]["samples"]) == 3
    assert first["saved_people"][1]["samples"][0]["event_id"] == event_ids[0]
    assert all(group["person_id"] != str(older_person.id) for group in first["groups"])
    assert first["groups"][0]["sightings"] == 20
    assert first["recordings_reviewed"] == 20
    assert first["next_offset"] == 20
    assert older["recordings_reviewed"] == 2
    assert older["next_offset"] is None
    assert str(first["groups"][0]["samples"][0]["event_id"]) == event_ids[-1]
    assert str(older["groups"][-1]["samples"][0]["event_id"]) == event_ids[0]
    assert client.get("/api/v1/face-detection/gallery?offset=-1").status_code == 422


def test_owner_approves_only_reviewed_suggestions_without_adding_samples(
    authenticated, config: Config, monkeypatch: pytest.MonkeyPatch
):
    client, headers = authenticated
    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    person = client.app.state.faces.people.create_samples("Known person", [feature])
    event_ids = [store(client.app.state.db, config) for _ in range(3)]
    with client.app.state.db.session() as session:
        for event_id in event_ids:
            session.add(FaceDetection(
                event_id=event_id, job_id=str(uuid4()),
                report=report().model_dump(mode="json"),
                created_at=datetime.now(UTC).isoformat(), elapsed_seconds=0.1,
            ))
        session.commit()

    async def synthetic_frame(_event_id: str, _offset_ms: int) -> bytes:
        return b"generated-sample"

    monkeypatch.setattr(client.app.state.faces, "sample_frame", synthetic_frame)
    monkeypatch.setattr("porchlight.faces.pipeline.feature_for_box", lambda *_: feature)
    gallery = client.get("/api/v1/face-detection/gallery").json()
    suggestions = gallery["suggestions"]
    assert len(suggestions) == 3
    assert gallery["groups"] == []
    assert {item["person_id"] for item in suggestions} == {str(person.id)}

    def selection(item: dict) -> dict:
        face = item["face"]
        return {key: face[key] for key in (
            "event_id", "offset_ms", "face_index", "frame_sha256", "box"
        )}

    payload = {"person_id": str(person.id), "faces": [selection(item) for item in suggestions[:2]]}
    saved = client.post("/api/v1/face-detection/suggestions/approve", headers=headers,
                        json=payload)
    assert saved.status_code == 200
    assert saved.json() == {"labeled": 2, "total_labeled": 2, "total_confirmed": 2}
    refreshed = client.get("/api/v1/face-detection/gallery").json()
    assert refreshed["labeled_totals"][str(person.id)] == 2
    assert refreshed["confirmed_totals"][str(person.id)] == 2
    assert client.app.state.faces.people.list().people[0].samples == 1
    for item in suggestions[:2]:
        face = client.app.state.faces.result(item["face"]["event_id"]).report.frames[0].faces[0]
        assert face.profile_id == person.id and face.match_score is None
    left_out = suggestions[2]["face"]["event_id"]
    assert client.app.state.faces.result(left_out).report.frames[0].faces[0].profile_id is None

    # A stale box aborts the entire request instead of labeling the remaining face.
    stale = client.post("/api/v1/face-detection/suggestions/approve", headers=headers,
                        json={"person_id": str(person.id), "faces": [
                            selection(suggestions[0]), selection(suggestions[2]),
                        ]})
    assert stale.status_code == 409
    assert client.app.state.faces.result(left_out).report.frames[0].faces[0].profile_id is None


def test_bulk_approval_accepts_203_faces_without_weakening_other_body_limits(
    authenticated, config: Config
):
    client, headers = authenticated
    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    person = client.app.state.faces.people.create_samples("Known person", [feature])
    event_id = store(client.app.state.db, config)
    box = FaceBox(x=10, y=15, width=30, height=40, score=0.95,
                  small=True, low_sharpness=True)
    frames = [FaceFrame(
        offset_ms=index * 250, sha256="a" * 64,
        width=320, height=240,
        faces=[box] * min(25, 203 - index * 25),
    ) for index in range(9)]
    with client.app.state.db.session() as session:
        session.add(FaceDetection(
            event_id=event_id, job_id=str(uuid4()),
            report=FaceReport(frames=frames).model_dump(mode="json"),
            created_at=datetime.now(UTC).isoformat(), elapsed_seconds=0.1,
        ))
        session.commit()
    selections = [{
        "event_id": event_id, "offset_ms": frame.offset_ms,
        "face_index": face_index, "frame_sha256": frame.sha256,
        "box": box.model_dump(mode="json"),
    } for frame in frames for face_index in range(len(frame.faces))]
    assert len(selections) == 203
    payload = {"person_id": str(person.id), "faces": selections}
    assert len(json.dumps(payload).encode()) > 16 * 1024
    assert client.post("/api/v1/face-detection/people/batch", headers=headers,
                       json=payload).status_code == 413
    response = client.post("/api/v1/face-detection/suggestions/approve",
                           headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "labeled": 203, "total_labeled": 203, "total_confirmed": 203,
    }
    saved = client.app.state.faces.result(event_id).report
    assert saved is not None
    assert sum(face.profile_id == person.id for frame in saved.frames
               for face in frame.faces) == 203
    assert client.app.state.faces.people.list().people[0].samples == 1
    oversized = client.post("/api/v1/face-detection/suggestions/approve",
                            headers=headers, content=b"x" * (1024 * 1024 + 1))
    assert oversized.status_code == 413


def test_owner_can_enroll_and_add_a_second_synthetic_sample(
    pipeline: FacePipeline, monkeypatch: pytest.MonkeyPatch
):
    if not pipeline.config.sface_model.is_file():
        pytest.skip("Optional SFace model not installed")
    event_id = store(pipeline.db, pipeline.config)
    with pipeline.db.session() as session:
        session.add(
            FaceDetection(
                event_id=event_id,
                job_id=str(uuid4()),
                report=report().model_dump(mode="json"),
                created_at=datetime.now(UTC).isoformat(),
                elapsed_seconds=0.1,
            )
        )
        session.commit()

    async def synthetic_frame(_event_id: str, _offset_ms: int) -> bytes:
        return b"generated-sample"

    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    monkeypatch.setattr(pipeline, "sample_frame", synthetic_frame)
    monkeypatch.setattr("porchlight.faces.pipeline.feature_for_box", lambda *_: feature)
    first = asyncio.run(pipeline.enroll(event_id, 0, 0, "Alex"))
    assert pipeline.result(event_id).report.frames[0].faces[0].profile_id == first.id
    assert pipeline.names_for_events([event_id]) == {event_id: ["Alex"]}
    second = asyncio.run(pipeline.enroll(event_id, 0, 0, None, first.id))
    assert first.id == second.id and second.samples == 2
    assert pipeline.people.vectors()[str(first.id)] == (feature, feature)
    envelope = pipeline.config.data_root / "secrets/faces.dpapi"
    assert envelope.is_file() and b"Alex" not in envelope.read_bytes()


def test_owner_can_assign_two_synthetic_faces_in_one_batch(
    pipeline: FacePipeline, monkeypatch: pytest.MonkeyPatch
):
    if not pipeline.config.sface_model.is_file():
        pytest.skip("Optional SFace model not installed")
    event_id = store(pipeline.db, pipeline.config)
    detected = report()
    detected.frames.append(detected.frames[0].model_copy(update={"offset_ms": 250}))
    with pipeline.db.session() as session:
        session.add(FaceDetection(
            event_id=event_id, job_id=str(uuid4()),
            report=detected.model_dump(mode="json"),
            created_at=datetime.now(UTC).isoformat(), elapsed_seconds=0.1,
        ))
        session.commit()

    async def synthetic_frame(_event_id: str, _offset_ms: int) -> bytes:
        return b"generated-sample"

    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    monkeypatch.setattr(pipeline, "sample_frame", synthetic_frame)
    monkeypatch.setattr("porchlight.faces.pipeline.feature_for_box", lambda *_: feature)
    selections = [
        FaceSelection(event_id=event_id, offset_ms=offset, face_index=0)
        for offset in (0, 250)
    ]
    profile = asyncio.run(pipeline.enroll_many(selections, "Alex"))
    assert profile.samples == 2
    assert len(pipeline.people.vectors()[str(profile.id)]) == 2
    saved = pipeline.result(event_id).report
    assert saved is not None
    assert all(frame.faces[0].profile_id == profile.id for frame in saved.frames)
    with pytest.raises(ValidationError):
        FaceEnrollmentBatch(samples=[selections[0], selections[0]], name="Alex")


def test_authenticated_batch_route_assigns_two_synthetic_faces(
    authenticated, config: Config, monkeypatch: pytest.MonkeyPatch
):
    client, headers = authenticated
    event_id = store(client.app.state.db, config)
    detected = report()
    detected.frames.append(detected.frames[0].model_copy(update={"offset_ms": 250}))
    with client.app.state.db.session() as session:
        session.add(FaceDetection(
            event_id=event_id, job_id=str(uuid4()),
            report=detected.model_dump(mode="json"),
            created_at=datetime.now(UTC).isoformat(), elapsed_seconds=0.1,
        ))
        session.commit()

    async def synthetic_frame(_event_id: str, _offset_ms: int) -> bytes:
        return b"generated-sample"

    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    monkeypatch.setattr(client.app.state.faces, "sample_frame", synthetic_frame)
    monkeypatch.setattr("porchlight.faces.pipeline.feature_for_box", lambda *_: feature)
    monkeypatch.setattr("porchlight.faces.pipeline.check_recognizer", lambda *_: None)
    response = client.post("/api/v1/face-detection/people/batch", headers=headers, json={
        "name": "Known person",
        "samples": [{"event_id": event_id, "offset_ms": offset, "face_index": 0}
                    for offset in (0, 250)],
    })
    assert response.status_code == 201
    assert response.json()["samples"] == 2
    assert response.json()["manual_samples"] == 2


def test_auto_samples_require_repeated_strong_matches_and_keep_manual_seed(
    pipeline: FacePipeline, monkeypatch: pytest.MonkeyPatch
):
    event_id = store(pipeline.db, pipeline.config)
    seed = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    close = tuple([0.8, 0.6] + [0.0] * 126)
    person = pipeline.people.create_samples("Known person", [seed] * 8)
    box = FaceBox(
        x=20, y=20, width=80, height=80, score=0.95,
        small=False, low_sharpness=False, profile_id=person.id, match_score=0.8,
    )
    frames = [FaceFrame(
        offset_ms=offset, sha256="a" * 64, width=320, height=240, faces=[box],
    ) for offset in (0, 250)]

    async def synthetic_frame(_event_id: str, _offset_ms: int) -> bytes:
        return b"generated-sample"

    monkeypatch.setattr(pipeline, "control", lambda: {"auto_enroll_enabled": True})
    monkeypatch.setattr(pipeline, "sample_frame", synthetic_frame)
    monkeypatch.setattr("porchlight.faces.pipeline.feature_for_box", lambda *_: close)
    assert asyncio.run(pipeline.maybe_add_automatic_samples(
        event_id, FaceReport(frames=frames[:1]),
    )) == 0
    report = FaceReport(frames=frames)
    weak = FaceReport(frames=[frame.model_copy(update={
        "faces": [box.model_copy(update={"match_score": 0.7})],
    }) for frame in frames])
    assert asyncio.run(pipeline.maybe_add_automatic_samples(event_id, weak)) == 0
    assert asyncio.run(pipeline.maybe_add_automatic_samples(event_id, report)) == 1
    assert asyncio.run(pipeline.maybe_add_automatic_samples(event_id, report)) == 0
    updated = pipeline.people.list().people[0]
    assert updated.samples == 9
    assert updated.manual_samples == 8
    assert updated.automatic_samples == 1
    assert pipeline.people.manual_vectors()[str(person.id)] == (seed,) * 8


def test_activity_names_follow_profile_rename_and_deletion(authenticated, config: Config):
    client, headers = authenticated
    event_id = store(client.app.state.db, config, summary="A person approached the door.")
    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    person = client.app.state.faces.people.create("Alex", feature)
    labeled = report()
    labeled.frames[0].faces[0].profile_id = person.id
    labeled.frames[0].faces[0].match_score = 0.72
    with client.app.state.db.session() as session:
        session.add(
            FaceDetection(
                event_id=event_id,
                job_id=str(uuid4()),
                report=labeled.model_dump(mode="json"),
                created_at=datetime.now(UTC).isoformat(),
                elapsed_seconds=0.1,
            )
        )
        session.commit()

    detail = client.get(f"/api/v1/events/{event_id}").json()
    assert detail["summary"] == "A person approached the door."
    assert detail["recognized_people"] == ["Alex"]
    assert any(
        item["id"] == event_id and item["recognized_people"] == ["Alex"]
        for item in client.get("/api/v1/events").json()["items"]
    )
    response = client.patch(
        f"/api/v1/face-detection/people/{person.id}",
        headers=headers,
        json={"name": "Sam"},
    )
    assert response.status_code == 200
    assert client.get(f"/api/v1/events/{event_id}").json()["recognized_people"] == ["Sam"]
    deleted = client.delete(f"/api/v1/face-detection/people/{person.id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/events/{event_id}").json()["recognized_people"] == []


def test_missing_model_cannot_enable(authenticated, config: Config):
    client, headers = authenticated
    client.app.state.faces.config = config.model_copy(update={"face_model": Path("missing-model")})
    assert not client.get("/api/v1/face-detection/status").json()["enabled"]
    assert (
        client.put(
            "/api/v1/face-detection/control",
            headers={"Origin": headers["Origin"]},
            json={"enabled": True},
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/api/v1/face-detection/control", headers=headers, json={"enabled": True}
        ).status_code
        == 409
    )
    assert not client.get("/api/v1/face-detection/status").json()["enabled"]
