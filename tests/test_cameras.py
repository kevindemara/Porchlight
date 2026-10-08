from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import CameraView
from porchlight.storage.models import Event, MediaAsset


def test_camera_evidence_and_preview_use_capture_time_and_survive_inventory_refresh(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, headers = authenticated
    imported = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    ).json()
    a, b, empty = [str(uuid4()) for _ in range(3)]
    inventory = [
        CameraView(
            id=identifier,
            name="Synthetic camera",
            family="doorbells",
            network_name="Fixture network",
            observed_armed=True,
        )
        for identifier in (a, b, empty)
    ]
    client.app.state.blink.cameras = inventory
    expected = str(uuid4())
    with client.app.state.db.session() as db:
        for camera, recorded, discovered, identifier, source in [
            (
                a,
                "2026-10-06T10:00:00+00:00",
                "2026-10-07T12:00:00+00:00",
                str(uuid4()),
                "blink_cloud",
            ),
            (a, "2026-10-06T11:00:00+00:00", "2026-10-06T11:00:00+00:00", expected, "blink_cloud"),
            (b, None, "2026-10-07T13:00:00+00:00", str(uuid4()), "blink_cloud"),
            (
                empty,
                "2026-10-08T12:00:00+00:00",
                "2026-10-08T12:00:00+00:00",
                str(uuid4()),
                "manual_import",
            ),
        ]:
            db.add(
                Event(
                    id=identifier,
                    source_type=source,
                    source_key=f"synthetic:{identifier}",
                    captured_at=recorded,
                    discovered_at=discovered,
                    timestamp_quality="upstream" if recorded else "unknown",
                    media_id=imported["media_id"],
                    analysis_status="not_analyzed",
                    camera_id=camera,
                )
            )
        db.commit()
    with client.app.state.db.session() as db:
        latest = db.get(Event, expected)
        latest.summary, latest.analysis_status = "Synthetic AI vehicle is visible.", "analyzed"
        db.commit()
    items = client.get("/api/v1/cameras").json()["items"]
    assert items[0]["recording_access"] == "cloud_archived"
    assert items[0]["latest_recording"]["event_id"] == expected
    assert items[0]["latest_recording"]["summary"] == "Synthetic AI vehicle is visible."
    assert items[0]["latest_recording"]["summary_source"] == "ai"
    assert items[0]["latest_recording"]["analysis_status"] == "analyzed"
    assert (
        client.patch(
            f"/api/v1/events/{expected}/annotation",
            headers=headers,
            json={
                "favourite": False,
                "note": "",
                "corrected_summary": "Synthetic owner description.",
            },
        ).status_code
        == 200
    )
    items = client.get("/api/v1/cameras").json()["items"]
    assert items[0]["latest_recording"]["summary_source"] == "owner"
    assert items[0]["latest_recording"]["summary"] == "Synthetic owner description."
    assert items[1]["latest_recording"]["captured_at"] is None
    assert items[2]["latest_recording"] is None
    assert items[2]["recording_access"] == "unverified"

    async def refresh() -> list[CameraView]:
        client.app.state.blink.cameras = inventory
        return inventory

    monkeypatch.setattr(client.app.state.blink, "discover_inventory", refresh)
    assert (
        client.post("/api/v1/integrations/blink/inventory/refresh", headers=headers).json()["items"]
        == items
    )
    assert client.post("/api/v1/integrations/blink/inventory/refresh").status_code == 403
    client.cookies.clear()
    assert client.get("/api/v1/cameras").status_code == 401


def test_thumbnail_is_real_jpeg_cached_private_and_never_served_without_source(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, headers = authenticated
    event = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    ).json()
    route = f"/api/v1/media/{event['media_id']}/thumbnail"
    first = client.get(route)
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/jpeg"
    assert first.headers["cache-control"] == "no-store"
    assert first.content.startswith(b"\xff\xd8") and first.content.endswith(b"\xff\xd9")
    assert len(first.content) < 512 * 1024
    monkeypatch.setattr(type(client.app.state.config), "tool_path", lambda self, name: None)
    assert client.get(route).content == first.content
    with client.app.state.db.session() as db:
        asset = db.get(MediaAsset, event["media_id"])
        assert asset is not None
        asset.relative_path = "../outside.mp4"
        db.commit()
    assert client.get(route).status_code == 404
    assert client.get(f"/api/v1/media/{uuid4()}/thumbnail").status_code == 404
    client.cookies.clear()
    assert client.get(route).status_code == 401
