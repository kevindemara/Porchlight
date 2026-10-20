import asyncio
import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError, HistoryControl
from porchlight.config import ROOT, Config
from porchlight.ingestion.history import history_id
from porchlight.ingestion.imports import Importer
from porchlight.ingestion.recordings import Recordings
from porchlight.providers.base import ClipReference, RecordingPage
from porchlight.providers.blink.recordings import media_path, normalize_page, retry_delay
from porchlight.storage.database import Database
from porchlight.storage.models import Event, Job, RecordingReference, RecordingScan
from sqlalchemy import func, select

NAMESPACE = "94d75fc3-8c8d-42df-bd15-5a6669ad347c"


class SyntheticProvider:
    recording_source_id = "synthetic-source"

    def __init__(self, data: bytes = b"not-video"):
        self.data = data
        self.fail_page: int | None = None
        self.page_count = 12
        self.downloads = 0

    async def recording_page(self, since: float, page: int) -> RecordingPage:
        if page == self.fail_page:
            raise ApiError(503, "SYNTHETIC_UNAVAILABLE", "Synthetic network failure.", True)
        if page > self.page_count:
            return RecordingPage([], True)
        # Every page repeats one record; these are distinct source events with shared bytes.
        return RecordingPage([self.clip(page), self.clip(1)], False)

    @staticmethod
    def clip(number: int) -> ClipReference:
        return ClipReference(
            f"blink_cloud:synthetic-{number}",
            "synthetic-camera",
            "2026-10-06T12:00:00+00:00",
            "2026-10-06T12:00:00Z",
            f"/api/v2/media/synthetic-{number}.mp4",
            False,
        )

    async def download_recording(self, path: str, destination: Path) -> None:
        self.downloads += 1
        destination.write_bytes(self.data)


@pytest.fixture
def recording_service(config: Config) -> tuple[Recordings, Database, SyntheticProvider]:
    db = Database(config.data_root)
    db.migrate()
    provider = SyntheticProvider()
    service = Recordings(config, db, provider, Importer(config, db))
    service.control(True)
    yield service, db, provider
    db.close()


def test_normalized_identity_does_not_depend_on_names_and_ambiguous_camera_stays_unknown() -> None:
    clip = {
        "id": 1,
        "created_at": "2026-10-06T12:00:00Z",
        "device_id": 3,
        "device_name": "Synthetic name",
        "media": "/api/v2/media/one.mp4",
    }
    first = normalize_page({"media": [clip]}, NAMESPACE, "synthetic-account", {"3": ["a"]})[0]
    second = normalize_page(
        {"media": [{**clip, "device_name": "Renamed"}]},
        NAMESPACE,
        "synthetic-account",
        {"3": ["a", "b"]},
    )[0]
    assert first.source_key == second.source_key
    assert first.camera_id == "a" and second.camera_id is None
    unknown = normalize_page(
        {"media": [{**clip, "created_at": "2026-10-06T12:00:00"}]},
        NAMESPACE,
        "synthetic-account",
        {},
    )[0]
    assert unknown.captured_at is None
    assert (
        normalize_page(
            {"media": [{"id": 2, "media_type": "thumbnail"}]}, NAMESPACE, "synthetic-account", {}
        )
        == []
    )


@pytest.mark.parametrize(
    "locator",
    [
        "https://evil.test/api/media",
        "//evil.test/api/media",
        "/api/a?token=synthetic",
        "/api/../private",
        "/api/%2e%2e/a",
        "file:///private",
        "/api/a#x",
        "/api/a\\b",
    ],
)
def test_private_signed_or_external_media_locator_is_rejected(locator: str) -> None:
    with pytest.raises(ApiError):
        media_path(locator)


def test_pagination_over_ten_pages_is_complete_and_duplicate_refs_are_idempotent(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
) -> None:
    service, db, provider = recording_service
    asyncio.run(service.discover(provider.recording_source_id))
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(RecordingReference)) == 12
        assert (
            session.scalar(
                select(func.count()).select_from(Job).where(Job.type == "blink_download")
            )
            == 12
        )
        scan = session.get(RecordingScan, provider.recording_source_id)
        assert scan and scan.page == 1 and scan.started_at is None and scan.checked_at


def test_routine_sync_finds_delayed_clips_behind_checkpoint_without_duplicates(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    synthetic_mp4: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, db, provider = recording_service
    provider.data = synthetic_mp4
    now = time.time()
    recorded = [now - 6 * 3600, now - 3 * 3600]
    clips = [
        replace(
            provider.clip(index + 1), captured_at=datetime.fromtimestamp(epoch, UTC).isoformat()
        )
        for index, epoch in enumerate(recorded)
    ]
    visible = 1
    cutoffs: list[float] = []

    async def delayed_page(since: float, page: int) -> RecordingPage:
        cutoffs.append(since)
        return RecordingPage(
            [
                clip
                for clip, epoch in zip(clips[:visible], recorded[:visible], strict=True)
                if epoch >= since
            ]
            if page == 1
            else [],
            exhausted=page > 1,
        )

    async def sync_and_download() -> None:
        await service.discover(provider.recording_source_id)
        with db.session() as session:
            downloads = list(
                session.scalars(
                    select(Job).where(Job.type == "blink_download", Job.status == "queued")
                )
            )
        for job in downloads:
            await service.execute(job)

    monkeypatch.setattr(provider, "recording_page", delayed_page)
    asyncio.run(sync_and_download())
    assert service.view().archived == 1 and provider.downloads == 1
    with db.session() as session:
        checkpoint = session.get(RecordingScan, provider.recording_source_id).since
    assert checkpoint > recorded[1]  # The three-hour-old clip appears only later.
    visible = 2
    asyncio.run(sync_and_download())
    assert service.view().archived == 2 and provider.downloads == 2
    assert cutoffs[-1] <= recorded[1]
    asyncio.run(sync_and_download())
    assert service.view().archived == 2 and provider.downloads == 2
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 2
        assert session.scalar(select(func.count()).select_from(RecordingReference)) == 2
        assert set(session.scalars(select(Event.captured_at))) == {
            clip.captured_at for clip in clips
        }
        assert set(session.scalars(select(Job.status).where(Job.type == "blink_download"))) == {
            "done"
        }


def test_failed_page_never_advances_checkpoint_and_restart_resumes(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    config: Config,
) -> None:
    service, db, provider = recording_service
    provider.fail_page = 2
    with db.session() as session:
        before = session.get(RecordingScan, provider.recording_source_id).since
    with pytest.raises(ApiError):
        asyncio.run(service.discover(provider.recording_source_id))
    with db.session() as session:
        scan = session.get(RecordingScan, provider.recording_source_id)
        assert scan.page == 2 and scan.since == before and scan.checked_at is None
    provider.fail_page = None
    provider.page_count = 2
    resumed = Recordings(config, db, provider, service.importer)
    asyncio.run(resumed.discover(provider.recording_source_id))
    assert resumed.view().discovered == 2
    assert not resumed.view().incomplete


def test_real_decoder_download_has_blink_provenance_and_preserves_distinct_events(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    synthetic_mp4: bytes,
) -> None:
    service, db, provider = recording_service
    provider.data = synthetic_mp4
    service.persist_page(
        provider.recording_source_id, RecordingPage([provider.clip(1), provider.clip(2)], True)
    )
    with db.session() as session:
        identifiers = list(session.scalars(select(RecordingReference.id)))
    for identifier in identifiers:
        asyncio.run(service.download(identifier))
    asyncio.run(service.download(identifiers[0]))
    assert provider.downloads == 2
    with db.session() as session:
        events = list(session.scalars(select(Event)))
        assert len(events) == 2
        assert events[0].media_id == events[1].media_id
        assert all(event.source_type == "blink_cloud" for event in events)
        assert all(event.camera_id == "synthetic-camera" for event in events)
        assert all(event.timestamp_quality == "upstream" for event in events)
    assert service.view().archived == 2


def test_fresh_blink_clip_and_generic_alert_work_with_no_ai_service(
    authenticated: tuple[TestClient, dict[str, str]],
    config: Config,
    synthetic_mp4: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, headers = authenticated
    assert not client.get("/api/v1/settings").json()["ai_enabled"]
    definition = json.loads(
        (ROOT / "examples/notification-rule.example.json").read_text(encoding="utf-8")
    )
    created = client.post(
        "/api/v1/notification-rules", headers=headers, json={"definition": definition}
    )
    assert created.status_code == 201, created.text
    provider = SyntheticProvider(synthetic_mp4)
    service = Recordings(config, client.app.state.db, provider, client.app.state.importer)
    service.control(True)
    clip = replace(provider.clip(1), captured_at=datetime.now(UTC).isoformat())
    service.persist_page(provider.recording_source_id, RecordingPage([clip], True))
    with client.app.state.db.session() as db:
        identifier = db.scalar(select(RecordingReference.id))
    asyncio.run(service.download(identifier))

    async def no_ai(*args: object, **kwargs: object) -> None:
        pytest.fail("The disabled automatic pipeline must not require an AI model")

    monkeypatch.setattr(client.app.state.analysis, "ready_model", no_ai)
    asyncio.run(client.app.state.analysis.schedule_new())
    event = client.get("/api/v1/events").json()["items"][0]
    assert event["camera_id"] == "synthetic-camera"
    assert event["source_type"] == "blink_cloud" and event["captured_at"] == clip.captured_at
    assert event["duration_seconds"] > 0 and event["analysis_status"] == "not_analyzed"
    assert event["recognized_people"] == [] and event["object_categories"] == []
    path = f"/api/v1/media/{event['media_id']}"
    assert client.get(path, headers={"Range": "bytes=0-15"}).status_code == 206
    assert client.get(path + "/thumbnail").status_code == 200
    client.app.state.notifications.dispatch()
    alerts = client.get("/api/v1/notifications").json()["items"]
    assert len(alerts) == 1 and alerts[0]["event_id"] == event["id"]
    assert "New camera activity" in alerts[0]["body"]


def test_interrupted_reference_commit_reuses_recovered_event(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    synthetic_mp4: bytes,
) -> None:
    service, db, provider = recording_service
    provider.data = synthetic_mp4
    service.persist_page(provider.recording_source_id, RecordingPage([provider.clip(1)], True))
    with db.session() as session:
        identifier = session.scalar(select(RecordingReference.id))
    asyncio.run(service.download(identifier))
    with db.session() as session:
        row = session.get(RecordingReference, identifier)
        row.state, row.event_id = "pending", None
        session.commit()
    asyncio.run(service.download(identifier))
    assert provider.downloads == 1
    assert service.view().archived == 1


def test_leases_pause_restart_and_server_retry_after(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, db, provider = recording_service
    claimed = service.claim()
    assert claimed is not None and claimed.status == "running"
    assert service.claim() is None
    resumed = Recordings(config, db, provider, service.importer)
    reclaimed = resumed.claim()
    assert reclaimed is not None and reclaimed.id == claimed.id

    async def limited(_: str) -> None:
        raise ApiError(429, "BLINK_RATE_LIMITED", "Synthetic rate limit.", True, 900)

    monkeypatch.setattr(resumed, "discover", limited)
    started = time.time()
    asyncio.run(resumed.execute(reclaimed))
    with db.session() as session:
        job = session.get(Job, claimed.id)
        assert job.available_at >= started + 900
        assert job.safe_error == "BLINK_RATE_LIMITED" and job.status == "queued"
    resumed.control(False)
    assert resumed.claim() is None
    assert retry_delay("900") == 900


def test_faster_cloud_poll_reschedules_only_healthy_discovery_on_restart(
    recording_service: tuple[Recordings, Database, SyntheticProvider], config: Config
) -> None:
    service, db, provider = recording_service
    now = time.time()
    with db.session() as session:
        scan = session.get(RecordingScan, provider.recording_source_id)
        scan.checked_at = now
        job = session.scalar(select(Job).where(Job.type == "blink_discover"))
        job.available_at = now + 120
        session.commit()
    faster = Recordings(
        config.model_copy(update={"cloud_poll_seconds": 30}), db, provider, service.importer
    )
    assert faster.view().poll_interval_seconds == 30
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "blink_discover"))
        assert job.available_at == now + 30
        job.available_at, job.safe_error, job.attempt = now + 900, "BLINK_RATE_LIMITED", 1
        session.commit()
    Recordings(config.model_copy(update={"cloud_poll_seconds": 30}), db, provider, service.importer)
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "blink_discover"))
        assert job.available_at == now + 900 and job.safe_error == "BLINK_RATE_LIMITED"


@pytest.mark.parametrize("source_type, expected", [("blink_cloud", 30), ("blink_local", 120)])
def test_successful_poll_uses_configured_cloud_interval_but_preserves_error_backoff(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
    source_type: str,
    expected: int,
) -> None:
    service, db, provider = recording_service
    config = config.model_copy(update={"cloud_poll_seconds": 30})
    worker = Recordings(config, db, provider, service.importer, source_type=source_type)
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "blink_discover"))
        job.payload = {**job.payload, "source_type": source_type}
        session.commit()
    provider.page_count = 0
    now = time.time() + 1
    monkeypatch.setattr("porchlight.ingestion.recordings.time", SimpleNamespace(time=lambda: now))
    monkeypatch.setattr("porchlight.ingestion.recordings.random.uniform", lambda _a, b: b)
    claimed = worker.claim()
    assert claimed
    asyncio.run(worker.execute(claimed))
    with db.session() as session:
        job = session.get(Job, claimed.id)
        assert job.available_at == now + expected + min(10, expected / 12)
        job.available_at = now
        session.commit()

    async def failed(_: str) -> None:
        raise ApiError(429, "BLINK_RATE_LIMITED", "Synthetic rate limit.", True, 900)

    monkeypatch.setattr(worker, "discover", failed)
    claimed = worker.claim()
    assert claimed
    asyncio.run(worker.execute(claimed))
    with db.session() as session:
        job = session.get(Job, claimed.id)
        assert job.available_at >= now + 900 and job.safe_error == "BLINK_RATE_LIMITED"


@pytest.mark.parametrize("clock_shift", [-3600, 3600])
def test_restart_after_clock_change_recovers_claimed_work_but_keeps_backoff(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
    clock_shift: int,
) -> None:
    service, db, provider = recording_service
    claimed = service.claim()
    assert claimed is not None
    original_now = time.time()
    deferred_until = original_now + 7200
    with db.session() as session:
        session.add(
            Job(
                id="synthetic-deferred",
                type="blink_discover",
                dedup_key="synthetic-deferred",
                payload={"source_id": provider.recording_source_id},
                status="queued",
                attempt=1,
                available_at=deferred_until,
                safe_error="BLINK_RATE_LIMITED",
            )
        )
        session.commit()
    # Change this service's clock only, never the PC clock or other test modules.
    monkeypatch.setattr(
        "porchlight.ingestion.recordings.time",
        SimpleNamespace(time=lambda: original_now + clock_shift),
    )
    resumed = Recordings(config, db, provider, service.importer)
    recovered = resumed.claim()
    assert recovered is not None and recovered.id == claimed.id
    assert recovered.attempt == claimed.attempt + 1
    assert resumed.claim() is None
    with db.session() as session:
        deferred = session.get(Job, "synthetic-deferred")
        assert deferred is not None and deferred.status == "queued"
        assert deferred.available_at == deferred_until and deferred.attempt == 1
        assert deferred.safe_error == "BLINK_RATE_LIMITED"
    assert provider.downloads == 0


def test_corrupt_download_stays_visible_as_a_failed_reference(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
) -> None:
    service, db, provider = recording_service
    service.persist_page(provider.recording_source_id, RecordingPage([provider.clip(1)], True))
    with db.session() as session:
        job = session.scalar(select(Job).where(Job.type == "blink_download"))
    asyncio.run(service.execute(job))
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        row = session.scalar(select(RecordingReference))
        assert row.state == "failed" and row.safe_error == "INVALID_MEDIA"
    assert not list(service.importer.media.glob("*.mp4"))


def test_recording_routes_require_auth_and_csrf(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    assert client.get("/api/v1/integrations/blink/recordings").status_code == 200
    assert (
        client.post(
            "/api/v1/integrations/blink/sync",
            headers={"Origin": headers["Origin"]},
            json={"enabled": True},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/integrations/blink/sync", headers=headers, json={"enabled": True}
        ).status_code
        == 409
    )
    client.cookies.clear()
    assert client.get("/api/v1/integrations/blink/recordings").status_code == 401


def test_api_to_background_worker_to_authenticated_playback(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
) -> None:
    client, headers = authenticated
    provider = SyntheticProvider(synthetic_mp4)
    provider.page_count = 1
    client.app.state.recordings.provider = provider
    response = client.post(
        "/api/v1/integrations/blink/sync", headers=headers, json={"enabled": True}
    )
    assert response.status_code == 202
    for _ in range(100):
        result = client.get("/api/v1/events").json()["items"]
        if result:
            break
        time.sleep(0.1)
    assert len(result) == 1
    event = result[0]
    assert event["source_type"] == "blink_cloud"
    assert event["camera_id"] == "synthetic-camera"
    assert event["analysis_status"] == "not_analyzed"
    playback = client.get(f"/api/v1/media/{event['media_id']}", headers={"Range": "bytes=0-15"})
    assert playback.status_code == 206 and playback.content == synthetic_mp4[:16]
    assert client.get("/api/v1/integrations/blink/recordings").json()["archived"] == 1
    client.post("/api/v1/integrations/blink/sync", headers=headers, json={"enabled": False})


def test_history_pause_discards_inflight_page_and_restart_resumes_saved_cursor(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, db, provider = recording_service
    service.control(False)
    service.history(HistoryControl(action="start", days=30))
    claimed = service.claim()
    assert claimed and claimed.type == "blink_history"
    original = provider.recording_page

    async def interrupted(since: float, page: int) -> RecordingPage:
        service.history(HistoryControl(action="pause"))
        return await original(since, page)

    monkeypatch.setattr(provider, "recording_page", interrupted)
    asyncio.run(service.execute(claimed))
    assert service.view().history.state == "paused" and service.view().discovered == 0
    with db.session() as session:
        scan = session.get(RecordingScan, history_id(provider.recording_source_id))
        assert scan and scan.page == 1 and scan.checked_at is None
    assert service.claim() is None
    monkeypatch.setattr(provider, "recording_page", original)
    provider.page_count, provider.fail_page = 2, 2
    service.history(HistoryControl(action="resume"))
    current = service.claim()
    assert current and current.payload["generation"] != claimed.payload["generation"]
    asyncio.run(service.execute(current))
    with db.session() as session:
        scan = session.get(RecordingScan, history_id(provider.recording_source_id))
        assert scan and scan.page == 2 and scan.checked_at is None
        job = session.get(Job, current.id)
        assert job and job.available_at > time.time()
        backoff = job.available_at
    service.history(HistoryControl(action="resume"))
    with db.session() as session:
        assert session.get(Job, current.id).available_at >= backoff
    provider.fail_page = None
    resumed = Recordings(config, db, provider, service.importer)
    with db.session() as session:
        generation = session.get(RecordingScan, history_id(provider.recording_source_id)).generation
    asyncio.run(resumed.discover_pages(provider.recording_source_id, generation))
    assert resumed.view().history.discovered == 2
    assert resumed.view().history.checked_at is not None


def test_history_range_reset_rejects_old_page_and_old_completion(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, db, provider = recording_service
    service.control(False)
    service.history(HistoryControl(action="start", days=30))
    old = service.claim()
    assert old

    async def reset(since: float, page: int) -> RecordingPage:
        service.history(HistoryControl(action="start", days=0))
        return RecordingPage([provider.clip(1)], True)

    monkeypatch.setattr(provider, "recording_page", reset)
    asyncio.run(service.execute(old))
    with db.session() as session:
        scan = session.get(RecordingScan, history_id(provider.recording_source_id))
        job = session.get(Job, old.id)
        assert scan and scan.since == 0 and scan.page == 1 and scan.checked_at is None
        assert job and job.status == "queued" and job.attempt == 0
        assert job.payload["generation"] == scan.generation != old.payload["generation"]
        assert session.scalar(select(func.count()).select_from(RecordingReference)) == 0


def test_history_keeps_fresh_provenance_and_downloads_new_history_silently(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
    synthetic_mp4: bytes,
) -> None:
    service, db, provider = recording_service
    provider.data = synthetic_mp4
    service.persist_page(provider.recording_source_id, RecordingPage([provider.clip(1)], True))
    service.history(HistoryControl(action="start", days=365))
    assert service.persist_page(
        provider.recording_source_id,
        RecordingPage([provider.clip(1), provider.clip(2)], True),
        historical=True,
    )
    with db.session() as session:
        references = list(
            session.scalars(select(RecordingReference).order_by(RecordingReference.source_key))
        )
        assert not references[0].historical and references[1].historical
        ids = [reference.id for reference in references]
    for identifier in ids:
        asyncio.run(service.download(identifier))
    service.control(False)
    service.history(HistoryControl(action="pause"))
    assert service.claim() is None
    with db.session() as session:
        events = list(session.scalars(select(Event).order_by(Event.source_key)))
        assert len(events) == 2 and not events[0].historical and events[1].historical
        assert events[0].media_id == events[1].media_id
        assert session.get(RecordingScan, provider.recording_source_id).checked_at
    assert service.view().history.archived == 1


def test_normal_recording_work_has_priority_over_history_and_pauses_independently(
    recording_service: tuple[Recordings, Database, SyntheticProvider],
) -> None:
    service, db, provider = recording_service
    service.history(HistoryControl(action="start", days=7))
    ordinary = service.claim()
    assert ordinary and ordinary.type == "blink_discover"
    service.control(False)
    history = service.claim()
    assert history and history.type == "blink_history"
    service.history(HistoryControl(action="pause"))
    assert service.claim() is None


def test_history_api_validates_ranges_and_requires_auth_and_csrf(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    url = "/api/v1/integrations/blink/history"
    assert (
        client.post(
            url, headers={"Origin": headers["Origin"]}, json={"action": "start"}
        ).status_code
        == 403
    )
    assert (
        client.post(url, headers=headers, json={"action": "start", "days": -1}).status_code == 422
    )
    assert (
        client.post(url, headers=headers, json={"action": "start", "days": 100000}).status_code
        == 422
    )
    assert (
        client.post(url, headers=headers, json={"action": "start", "days": 30}).status_code == 409
    )
    client.cookies.clear()
    assert client.post(url, headers=headers, json={"action": "start"}).status_code == 401
