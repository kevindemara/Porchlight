from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from porchlight.storage.models import Capture, Event, Job, MediaAsset


def old_event(client: TestClient, headers: dict[str, str], video: bytes) -> dict:
    return dict(
        client.post(
            "/api/v1/imports",
            headers={
                **headers,
                "Content-Type": "video/mp4",
                "X-Recorded-At": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
            },
            content=video,
        ).json()
    )


def capture(client: TestClient, *, favourite: bool = False, state: str = "ready") -> str:
    identifier = str(uuid4())
    with client.app.state.db.session() as db:
        db.add(
            Capture(
                id=identifier,
                camera_id="synthetic",
                camera_name="Synthetic camera",
                kind="snapshot",
                state=state,
                saved_at=(datetime.now(UTC) - timedelta(days=60)).isoformat(),
                bytes=5,
                width=1,
                height=1,
                favourite=favourite,
            )
        )
        db.commit()
    client.app.state.library.path(identifier, ".jpg").write_bytes(b"owned")
    return identifier


def test_cleanup_preview_preserves_favourites_busy_and_shared_files(
    authenticated,
    synthetic_mp4,
) -> None:
    client, headers = authenticated
    original = old_event(client, headers, synthetic_mp4)
    kept = str(uuid4())
    with client.app.state.db.session() as db:
        db.add(
            Event(
                id=kept,
                source_key="synthetic:shared",
                source_type="blink_cloud",
                media_id=original["media_id"],
                captured_at=datetime.now(UTC).isoformat(),
                discovered_at=datetime.now(UTC).isoformat(),
                timestamp_quality="upstream",
                analysis_status="not_analyzed",
                favourite=True,
            )
        )
        db.commit()
    removable = capture(client)
    pinned = capture(client, favourite=True)
    active = capture(client, state="saving")
    preview = client.post("/api/v1/retention/preview", headers=headers, json={"days": 30}).json()
    assert preview["event_count"] == 1 and preview["capture_count"] == 1
    assert preview["reclaimable_bytes"] == 5
    assert preview["protected_count"] == 1 and preview["busy_count"] == 1
    assert client.get(f"/api/v1/events/{original['id']}").status_code == 200
    assert (
        client.post("/api/v1/retention/apply", json={"token": preview["token"]}).status_code == 403
    )
    result = client.post(
        "/api/v1/retention/apply", headers=headers, json={"token": preview["token"]}
    ).json()
    assert result == {"events_deleted": 1, "captures_deleted": 1, "automatic_enabled": False}
    assert client.get(f"/api/v1/media/{original['media_id']}").content == synthetic_mp4
    assert client.get(f"/api/v1/events/{kept}").status_code == 200
    assert not client.app.state.library.path(removable, ".jpg").exists()
    assert client.app.state.library.path(pinned, ".jpg").exists()
    assert client.app.state.library.path(active, ".jpg").exists()
    assert (
        client.post(
            "/api/v1/retention/apply", headers=headers, json={"token": preview["token"]}
        ).status_code
        == 409
    )


def test_changed_or_expired_preview_cannot_delete_and_enable_requires_review(
    authenticated,
    synthetic_mp4,
) -> None:
    client, headers = authenticated
    original = old_event(client, headers, synthetic_mp4)
    settings = client.get("/api/v1/settings").json()
    assert (
        client.put(
            "/api/v1/settings", headers=headers, json={**settings, "retention_enabled": True}
        ).json()["code"]
        == "RETENTION_PREVIEW_REQUIRED"
    )
    preview = client.post("/api/v1/retention/preview", headers=headers, json={"days": 30}).json()
    client.patch(
        f"/api/v1/events/{original['id']}/annotation",
        headers=headers,
        json={"favourite": True, "note": "keep"},
    )
    assert (
        client.post(
            "/api/v1/retention/apply", headers=headers, json={"token": preview["token"]}
        ).json()["code"]
        == "PREVIEW_CHANGED"
    )
    preview = client.post("/api/v1/retention/preview", headers=headers, json={"days": 30}).json()
    reviewed = client.app.state.retention.previews[preview["token"]]
    client.app.state.retention.previews[preview["token"]] = (0, *reviewed[1:])
    assert (
        client.post(
            "/api/v1/retention/apply", headers=headers, json={"token": preview["token"]}
        ).json()["code"]
        == "PREVIEW_EXPIRED"
    )
    assert client.get(f"/api/v1/events/{original['id']}").status_code == 200
    preview = client.post("/api/v1/retention/preview", headers=headers, json={"days": 30}).json()
    assert (
        client.post(
            "/api/v1/retention/apply",
            headers=headers,
            json={"token": preview["token"], "enable_automatic": True},
        ).status_code
        == 200
    )
    client.app.state.retention.last_run = 0
    client.app.state.retention.maintain()
    assert client.get(f"/api/v1/events/{original['id']}").status_code == 200
    assert client.get("/api/v1/settings").json()["retention_enabled"]
    removable = capture(client)
    client.app.state.retention.last_run = 0
    client.app.state.retention.maintain()
    assert not client.app.state.library.path(removable, ".jpg").exists()


def test_capture_favourite_busy_delete_and_configured_budget(authenticated, synthetic_mp4) -> None:
    client, headers = authenticated
    identifier = capture(client)
    assert client.patch(
        f"/api/v1/library/{identifier}/favourite", headers=headers, json={"favourite": True}
    ).json()["favourite"]
    active = capture(client, state="recording")
    assert client.delete(f"/api/v1/library/{active}", headers=headers).status_code == 409
    assert client.delete(f"/api/v1/library/{identifier}", headers=headers).status_code == 204
    assert not client.app.state.library.path(identifier, ".jpg").exists()
    original = old_event(client, headers, synthetic_mp4)
    with client.app.state.db.session() as db:
        asset = db.get(MediaAsset, original["media_id"])
        asset.bytes = 50 * 1024**3
        db.commit()
    response = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    )
    assert response.json()["code"] == "ARCHIVE_BUDGET_REACHED"
    assert client.get(f"/api/v1/events/{original['id']}").status_code == 200


def test_active_analysis_is_omitted_from_cleanup_preview(authenticated, synthetic_mp4) -> None:
    client, headers = authenticated
    original = old_event(client, headers, synthetic_mp4)
    with client.app.state.db.session() as db:
        job_id = str(uuid4())
        db.add(
            Job(
                id=job_id,
                type="ai_analyze",
                dedup_key=job_id,
                payload={"event_id": original["id"]},
                status="running",
                attempt=1,
                available_at=0,
            )
        )
        db.commit()
    preview = client.post("/api/v1/retention/preview", headers=headers, json={"days": 30}).json()
    assert preview["busy_count"] == 1 and preview["event_count"] == 0
    assert client.get(f"/api/v1/events/{original['id']}").status_code == 200
