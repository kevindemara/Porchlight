import asyncio
import copy
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from porchlight.api.contracts import ApiError, BlinkStatus
from porchlight.ingestion.imports import Importer
from porchlight.ingestion.recordings import Recordings
from porchlight.providers.blink import local_storage
from porchlight.providers.blink.adapter import BlinkAdapter
from porchlight.providers.blink.local_storage import LocalStorageSource, normalize_manifest
from porchlight.storage.database import Database
from porchlight.storage.models import Event, Job, RecordingReference
from sqlalchemy import func, select
from test_blink_adapter import SyntheticBlink, SyntheticVault
from test_recordings import SyntheticProvider

NAMESPACE = "e54e9a8e-cb6c-41dd-b78f-1580dbf51742"
MODULE = "bb8e1306-8fe7-4c87-bdcb-1f312478b097"
MANIFEST = {
    "manifest_id": 1,
    "clips": [
        {
            "id": 7,
            "camera_name": "Syntheticcamera",
            "created_at": "2026-10-07T12:00:00Z",
            "size": 1200,
        },
        {
            "id": 8,
            "camera_name": "duplicatename",
            "created_at": "2026-10-07T12:00:00",
            "size": 1400,
        },
    ],
}


def test_manifest_identity_survives_generation_and_unknown_timestamps_are_preserved() -> None:
    _, items = normalize_manifest(
        MANIFEST,
        NAMESPACE,
        "10",
        MODULE,
        {"Syntheticcamera": ["camera-one"], "duplicatename": ["camera-two", "camera-three"]},
    )
    _, again = normalize_manifest({**MANIFEST, "manifest_id": 99}, NAMESPACE, "10", MODULE, {})
    assert [item["key"] for item in items] == [item["key"] for item in again]
    assert items[0]["camera_id"] == "camera-one" and items[0]["captured_at"] is not None
    assert items[1]["camera_id"] is None and items[1]["captured_at"] is None
    assert items[1]["raw_timestamp"] == "2026-10-07T12:00:00"
    for body in (
        {"clips": []},
        {**MANIFEST, "manifest_id": "../path"},
        {**MANIFEST, "clips": [{}]},
        {**MANIFEST, "clips": MANIFEST["clips"] * 5001},
    ):
        with pytest.raises(ApiError):
            normalize_manifest(body, NAMESPACE, "10", MODULE, {})


def adapter_fixture(config, db) -> BlinkAdapter:
    provider = BlinkAdapter(db, SyntheticVault())
    provider.status = BlinkStatus(state="connected", message="Synthetic connected")
    blink = SyntheticBlink(refresh_rate=120)
    blink.account_id = 10
    blink.auth = SimpleNamespace(data={}, login_attributes={"token": "synthetic"})
    blink.homescreen = {
        "networks": [{"id": 3, "name": "Synthetic network", "armed": True}],
        "cameras": [{"id": 7, "network_id": 3, "name": "Synthetic camera", "enabled": True}],
        "sync_modules": [
            {
                "id": 2,
                "network_id": 3,
                "name": "Synthetic module",
                "local_storage_enabled": True,
                "local_storage_compatible": True,
                "local_storage_status": "active",
            }
        ],
    }
    provider.blink = blink
    provider.refresh_if_needed = AsyncMock()
    return provider


def test_module_workflow_coalesces_manifests_persists_requests_and_survives_restart(
    config, monkeypatch, synthetic_mp4
) -> None:
    db = Database(config.data_root)
    db.migrate()
    calls = {"request": 0, "poll": 0, "prepare": 0, "download": 0}

    async def request(blink, network, module):
        assert network == 3 and module == 2
        calls["request"] += 1
        return {"id": 42}

    async def poll(blink, network, module, request_id):
        assert str(request_id) == "42"
        calls["poll"] += 1
        return copy.deepcopy(MANIFEST)

    async def prepare(blink, network, module, manifest, clip):
        assert (network, module, str(manifest), str(clip)) == (3, 2, "1", "7")
        calls["prepare"] += 1
        return {"id": 123}

    monkeypatch.setattr(local_storage.upstream_api, "request_local_storage_manifest", request)
    monkeypatch.setattr(local_storage.upstream_api, "get_local_storage_manifest", poll)
    monkeypatch.setattr(local_storage.upstream_api, "request_local_storage_clip", prepare)

    async def run() -> None:
        provider = adapter_fixture(config, db)
        await provider.read_inventory()
        source = LocalStorageSource(provider)
        assert len(provider.local_targets) == 1
        first, second = await asyncio.gather(
            source.recording_page(0, 1), source.recording_page(0, 1)
        )
        assert first == second and len(first.clips) == 2 and first.exhausted
        assert calls["request"] == 1 and calls["poll"] == 1
        assert first.clips[0].camera_id == provider.cameras[0].id
        assert first.clips[0].source_key.startswith("blink_local:")
        module = next(iter(provider.local_targets))
        persisted = source.state(module)
        assert persisted["request_id"] is None
        source.save(module, {"started": time.time(), "request_id": "42"})
        restarted = LocalStorageSource(provider)
        third = await restarted.recording_page(0, 1)
        assert third == first and calls["request"] == 1 and calls["poll"] == 2

        async def download(path: str, destination: Path):
            assert (
                path == "/api/v1/accounts/10/networks/3/sync_modules/2"
                "/local_storage/manifest/1/clip/request/7"
            )
            assert provider.lock.locked()
            calls["download"] += 1
            destination.write_bytes(synthetic_mp4)

        provider.download_locked = download
        await source.download_recording(
            first.clips[0].media_path, config.data_root / "synthetic-one.part"
        )
        await source.download_recording(
            first.clips[0].media_path, config.data_root / "synthetic-two.part"
        )
        assert calls["prepare"] == 1 and calls["download"] == 2
        with pytest.raises(ApiError):
            await source.download_recording("https://evil.invalid", config.data_root / "never.part")
        assert calls["download"] == 2
        source.save(module, {"started": time.time(), "request_id": None})
        with pytest.raises(ApiError) as error:
            await source.recording_page(0, 1)
        assert error.value.code == "LOCAL_MODULE_WAIT" and calls["request"] == 1
        await provider.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_separate_workers_do_not_block_each_other_and_local_events_use_correct_provenance(
    config, synthetic_mp4
) -> None:
    db = Database(config.data_root)
    db.migrate()
    cloud = SyntheticProvider(synthetic_mp4)
    local = SyntheticProvider(synthetic_mp4)
    local.recording_source_id = "synthetic-local-source"
    importer = Importer(config, db)
    cloud_worker = Recordings(config, db, cloud, importer)
    local_worker = Recordings(config, db, local, importer, "blink_local")
    cloud_worker.control(True)
    local_worker.control(True)
    claimed_cloud = cloud_worker.claim()
    claimed_local = local_worker.claim()
    assert claimed_cloud and claimed_local and claimed_cloud.id != claimed_local.id
    with db.session() as session:
        assert all(row.status == "running" for row in session.scalars(select(Job)))
    clip = SyntheticProvider.clip(1)
    from dataclasses import replace

    from porchlight.providers.base import RecordingPage

    local_worker.persist_page(
        local.recording_source_id,
        RecordingPage([replace(clip, source_key="blink_local:synthetic-local-clip")], True),
    )
    with db.session() as session:
        reference = session.scalar(select(RecordingReference))
        identifier = reference.id
        assert reference.source_type == "blink_local"
    asyncio.run(local_worker.download(identifier))
    with db.session() as session:
        event = session.scalar(select(Event))
        assert event.source_type == "blink_local"
        assert session.scalar(select(func.count()).select_from(Event)) == 1
    assert local_worker.view().source == "blink_local" and not local_worker.view().no_plan_verified
    db.close()


def test_local_storage_api_is_capability_gated_and_requires_auth_csrf(authenticated) -> None:
    client, headers = authenticated
    status = client.get("/api/v1/integrations/blink/local-recordings").json()
    assert not status["eligible"] and status["sync"]["source"] == "blink_local"
    assert (
        client.post("/api/v1/integrations/blink/local-sync", json={"enabled": True}).status_code
        == 403
    )
    denied = client.post(
        "/api/v1/integrations/blink/local-sync", headers=headers, json={"enabled": True}
    )
    assert denied.status_code == 409 and denied.json()["code"] == "LOCAL_STORAGE_NOT_READY"
    client.cookies.clear()
    assert client.get("/api/v1/integrations/blink/local-recordings").status_code == 401


def test_missing_media_retries_existing_transfer_and_auth_failure_pauses_account(
    config, monkeypatch
) -> None:
    db = Database(config.data_root)
    db.migrate()
    posts = 0

    async def prepare(*args):
        nonlocal posts
        posts += 1
        return {"id": 1}

    monkeypatch.setattr(local_storage.upstream_api, "request_local_storage_clip", prepare)

    async def run() -> None:
        provider = adapter_fixture(config, db)
        await provider.read_inventory()
        source = LocalStorageSource(provider)
        module = next(iter(provider.local_targets))
        manifest, clips = normalize_manifest(MANIFEST, provider.namespace, "10", module, {})
        source.save(
            module, {"started": time.time(), "clips": clips, "manifest": manifest, "prepared": {}}
        )

        async def not_ready(path, destination):
            raise ApiError(410, "SOURCE_MEDIA_EXPIRED", "Synthetic not ready.")

        provider.download_locked = not_ready
        locator = f"local:{module}:{clips[0]['key']}"
        for _ in range(2):
            with pytest.raises(ApiError) as error:
                await source.download_recording(locator, config.data_root / "never.part")
            assert error.value.code == "LOCAL_TRANSFER_UNAVAILABLE" and error.value.retryable
        assert posts == 1
        source.save(module, {"started": time.time(), "clips": [], "manifest": manifest})
        with pytest.raises(ApiError) as error:
            await source.download_recording(locator, config.data_root / "never.part")
        assert error.value.code == "SOURCE_MEDIA_EXPIRED"

        async def unauthorized():
            raise local_storage.UnauthorizedError("synthetic-private-upstream-error")

        provider.refresh_if_needed = unauthorized
        with pytest.raises(ApiError) as error:
            await source.recording_page(0, 1)
        assert error.value.code == "BLINK_AUTH_REQUIRED"
        assert provider.status.state == "reauth_required"
        assert "synthetic-private" not in error.value.message
        await provider.close()

    try:
        asyncio.run(run())
    finally:
        db.close()
