import asyncio
import hashlib
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from porchlight.ai.frames import extract_frames
from porchlight.config import Config
from porchlight.storage.models import Event, MediaAsset
from sqlalchemy import select


def test_jpeg_import_preserves_original_and_protects_image_routes(
    authenticated: tuple[TestClient, dict[str, str]], synthetic_jpeg: bytes, config: Config
) -> None:
    client, headers = authenticated
    marker = b"SYNTHETIC-EXIF-NOT-FOR-INFERENCE"
    image = (
        synthetic_jpeg[:2]
        + b"\xff\xe1"
        + (len(marker) + 2).to_bytes(2, "big")
        + marker
        + synthetic_jpeg[2:]
    )
    first = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "image/jpeg"}, content=image
    )
    assert first.status_code == 201, first.text
    event = first.json()
    assert event["media_type"] == "image/jpeg" and event["duration_seconds"] == 0
    assert event["captured_at"] is None and event["analysis_status"] == "not_analyzed"
    assert (
        client.post(
            "/api/v1/imports", headers={**headers, "Content-Type": "image/jpeg"}, content=image
        ).json()["id"]
        == event["id"]
    )
    route = f"/api/v1/media/{event['media_id']}"
    response = client.get(route)
    assert response.content == image and response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-store"
    assert client.get(route, headers={"Range": "bytes=0-15"}).content == image[:16]
    thumbnail = client.get(route + "/thumbnail")
    assert thumbnail.status_code == 200 and marker not in thumbnail.content
    with client.app.state.db.session() as db:
        asset = db.get(MediaAsset, event["media_id"])
        assert asset and asset.relative_path.endswith(".jpg")
        frames = asyncio.run(
            extract_frames(config.data_root / asset.relative_path, 0, config, "image/jpeg")
        )
    assert len(frames) == 1 and frames[0].offset_ms == 0
    assert marker not in frames[0].image
    assert client.delete(f"/api/v1/events/{event['id']}", headers=headers).status_code == 204
    assert client.get(route).status_code == 404
    imported = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "image/jpeg"}, content=image
    ).json()
    client.cookies.clear()
    assert client.get(f"/api/v1/media/{imported['media_id']}").status_code == 401
    assert client.head(f"/api/v1/media/{imported['media_id']}").status_code == 401


def test_invalid_jpeg_and_concatenated_images_do_not_create_events(
    authenticated: tuple[TestClient, dict[str, str]], synthetic_jpeg: bytes
) -> None:
    client, headers = authenticated
    for image in (b"<html>not a JPEG</html>", b"\xff\xd8\xffinvalid", synthetic_jpeg * 2):
        response = client.post(
            "/api/v1/imports", headers={**headers, "Content-Type": "image/jpeg"}, content=image
        )
        assert response.status_code == 422, response.text
    assert client.get("/api/v1/events").json()["items"] == []


def test_import_is_playable_idempotent_and_not_analyzed(
    authenticated: tuple[TestClient, dict[str, str]], synthetic_mp4: bytes
) -> None:
    client, headers = authenticated
    headers = {**headers, "Content-Type": "video/mp4"}
    first = client.post("/api/v1/imports", headers=headers, content=synthetic_mp4)
    assert first.status_code == 201, first.text
    event = first.json()
    assert event["source_type"] == "manual_import"
    assert event["captured_at"] is None
    assert event["timestamp_quality"] == "unknown"
    assert event["analysis_status"] == "not_analyzed"
    second = client.post("/api/v1/imports", headers=headers, content=synthetic_mp4)
    assert second.json()["id"] == event["id"]
    assert len(client.get("/api/v1/events").json()["items"]) == 1
    path = f"/api/v1/media/{event['media_id']}"
    assert client.get(path).content == synthetic_mp4
    partial = client.get(path, headers={"Range": "bytes=0-15"})
    assert partial.status_code == 206
    assert partial.content == synthetic_mp4[:16]
    assert client.head(path).status_code == 200
    assert client.get(path, headers={"Range": "bytes=999999999-"}).status_code == 416
    with client.app.state.db.session() as db:
        asset = db.get(MediaAsset, event["media_id"])
        assert asset is not None
        (client.app.state.config.data_root / asset.relative_path).unlink()
    repaired = client.post("/api/v1/imports", headers=headers, content=synthetic_mp4)
    assert repaired.status_code == 201
    assert repaired.json()["id"] == event["id"]
    assert client.get(path).content == synthetic_mp4
    client.cookies.clear()
    assert client.get(path, headers={"Range": "bytes=0-15"}).status_code == 401
    assert client.head(path).status_code == 401


def test_invalid_mp4_cannot_create_event(authenticated: tuple[TestClient, dict[str, str]]) -> None:
    client, headers = authenticated
    response = client.post(
        "/api/v1/imports",
        headers={**headers, "Content-Type": "video/mp4"},
        content=b"<html>not a video</html>",
    )
    assert response.status_code == 422
    assert client.get("/api/v1/events").json()["items"] == []


def test_annotation_and_literal_search(
    authenticated: tuple[TestClient, dict[str, str]], synthetic_mp4: bytes
) -> None:
    client, headers = authenticated
    event = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    ).json()
    annotated = client.patch(
        f"/api/v1/events/{event['id']}/annotation",
        headers=headers,
        json={"note": "literal 100% sample", "favourite": True},
    )
    assert annotated.status_code == 200
    assert len(client.get("/api/v1/events", params={"query": "100%"}).json()["items"]) == 1
    assert len(client.get("/api/v1/events", params={"query": "%"}).json()["items"]) == 1
    assert client.get("/api/v1/events", params={"query": "inexistent"}).json()["items"] == []


def test_import_journal_recovers_after_promotion(
    client: TestClient, config: Config, synthetic_mp4: bytes
) -> None:
    sha = hashlib.sha256(synthetic_mp4).hexdigest()
    (config.data_root / "media" / f"{sha}.mp4").write_bytes(synthetic_mp4)
    manifest = {
        "source_key": f"manual:{sha}:unknown",
        "sha256": sha,
        "bytes": len(synthetic_mp4),
        "captured_at": None,
        "discovered_at": "2026-10-06T12:00:00+00:00",
        "duration_seconds": 1,
        "width": 320,
        "height": 240,
    }
    journal = config.data_root / "tmp" / "recovery.import.json"
    journal.write_text(json.dumps(manifest))
    assert client.app.state.importer.recover() == 1
    assert not journal.exists()
    with client.app.state.db.session() as db:
        assert db.scalar(select(Event)) is not None
    assert client.app.state.importer.recover() == 0


def test_media_containment_blocks_arbitrary_files(
    authenticated: tuple[TestClient, dict[str, str]], config: Config
) -> None:
    client, _ = authenticated
    outside = config.data_root.parent / "outside.mp4"
    outside.write_bytes(b"PRIVATE-SHOULD-NOT-BE-SERVED")
    identifier = str(uuid4())
    with client.app.state.db.session() as db:
        db.add(
            MediaAsset(
                id=identifier,
                sha256="synthetic",
                relative_path="../outside.mp4",
                bytes=20,
                duration_seconds=1,
                width=1,
                height=1,
            )
        )
        db.commit()
    response = client.get(f"/api/v1/media/{identifier}")
    assert response.status_code == 404
    assert b"PRIVATE-SHOULD-NOT-BE-SERVED" not in response.content
