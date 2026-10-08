import asyncio
import time
from contextlib import suppress
from types import SimpleNamespace
from unittest.mock import AsyncMock

from porchlight.api.contracts import AnalysisStatus
from porchlight.storage.models import Event, IntegrationState, Job, MediaAsset, SettingsRow


def test_allowlist_export_excludes_all_private_text_and_reports_missing_file(
    authenticated, synthetic_mp4
) -> None:
    client, headers = authenticated
    event = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    ).json()
    sensitive = "SYNTHETIC-PRIVATE-SENTINEL"
    with client.app.state.db.session() as session:
        session.get(Event, event["id"]).note = sensitive
        session.get(Event, event["id"]).labels_summary = sensitive
        session.get(Event, event["id"]).corrected_entities = [
            {"category": "other", "private": sensitive}
        ]
        asset = session.get(MediaAsset, event["media_id"])
        asset.relative_path = (
            f"media/{sensitive}.mp4"  # Missing, but its path must never be exported.
        )
        session.add(IntegrationState(id=sensitive, values={"token": sensitive, "name": sensitive}))
        row = session.get(SettingsRow, 1)
        row.values = {**row.values, "ai_model": sensitive}
        session.commit()
    response = client.get("/api/v1/diagnostics/export")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
    assert (
        sensitive not in response.text
        and str(client.app.state.config.data_root) not in response.text
    )
    report = response.json()
    assert report["counts"]["events"] == 1
    assert report["media_check"] == {
        "checked": 1,
        "missing": 1,
        "invalid_paths": 0,
        "bounded": False,
    }
    assert report["schema"] == "0018"
    client.cookies.clear()
    assert client.get("/api/v1/diagnostics/export").status_code == 401


def test_health_uses_actual_reserve_budget_and_persistent_model_readiness(
    authenticated, monkeypatch
) -> None:
    client, _ = authenticated
    with client.app.state.db.session() as session:
        row = session.get(SettingsRow, 1)
        row.values = {**row.values, "reserve_gib": 1, "archive_budget_gib": 5}
        session.commit()
    client.app.state.analysis.view = AsyncMock(
        return_value=AnalysisStatus(
            enabled=False,
            ready=True,
            cloud_disabled=True,
            model="synthetic",
            message="Ready from persisted test.",
            queued=0,
            running=0,
            completed=0,
            failed=0,
        )
    )
    monkeypatch.setattr(
        "porchlight.app.shutil.disk_usage", lambda path: SimpleNamespace(free=2 * 1024**3)
    )
    status = client.get("/api/v1/health").json()
    assert status["archive"]["state"] == "ready"  # No hardcoded 5 GiB reserve.
    assert status["reserve_bytes"] == 1024**3
    assert status["ai"]["state"] == "ready" and client.app.state.ai_test is None
    with client.app.state.db.session() as session:
        session.add(
            MediaAsset(
                id="synthetic",
                sha256="synthetic",
                relative_path="media/missing.mp4",
                bytes=5 * 1024**3,
                duration_seconds=1,
                width=1,
                height=1,
            )
        )
        session.commit()
    assert client.get("/api/v1/health").json()["archive"]["state"] == "unavailable"


def test_dead_worker_and_failed_listing_are_visible_despite_live_server(authenticated) -> None:
    client, _ = authenticated
    private = "SYNTHETIC-PRIVATE-ERROR"
    with client.app.state.db.session() as session:
        session.add(
            Job(
                id="synthetic-listing",
                type="blink_discover",
                dedup_key="synthetic-listing",
                payload={"private": private},
                status="failed",
                attempt=5,
                available_at=time.time(),
                safe_error=private,
            )
        )
        session.commit()

    async def stop_only_synthetic_worker() -> None:
        task = client.app.state.workers["analysis"]
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    client.portal.call(stop_only_synthetic_worker)
    assert client.get("/health/live").status_code == 200
    response = client.get("/api/v1/health")
    assert response.status_code == 200 and private not in response.text
    rows = {row["key"]: row for row in response.json()["checks"]}
    assert rows["worker_analysis"]["state"] == "unavailable"
    assert rows["worker_analysis"]["safe_error"] == "WORKER_STALE"
    assert rows["listing"]["state"] == "unavailable" and rows["listing"]["needs_attention"] == 1
    assert rows["downloads"]["state"] == "unverified"  # A listing is not a saved video.
    assert rows["inventory"]["last_success_at"] is None
    assert rows["push"]["state"] == "not_configured"
