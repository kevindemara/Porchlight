import asyncio
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.ingestion.fragments import Fragments
from porchlight.library import MAX_SNAPSHOT, Library, jpeg_size
from porchlight.live import Session
from porchlight.security.auth import COOKIE, digest
from porchlight.storage.database import Database
from porchlight.storage.models import Capture


@pytest.fixture
def pixels(config: Config, tmp_path: Path) -> tuple[bytes, bytes]:
    executable = config.tool_path("ffmpeg")
    if not executable:
        pytest.skip("Configure FFmpeg to run native capture checks")
    video, image = tmp_path / "generated.mp4", tmp_path / "generated.jpg"
    subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=12:duration=4",
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-g",
            "12",
            "-bf",
            "0",
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            str(video),
        ],
        check=True,
        timeout=30,
    )
    subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=orange:s=320x240",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(image),
        ],
        check=True,
        timeout=30,
    )
    return video.read_bytes(), image.read_bytes()


def segments(data: bytes) -> tuple[bytes, list[bytes]]:
    parser = Fragments()
    parts = []
    for offset in range(0, len(data), 17):
        parts.extend(fragment for _, fragment in parser.feed(data[offset : offset + 17]))
    return parser.header, parts


def test_midstream_capture_is_playable_trimmed_and_restart_recoverable(
    config: Config, pixels: tuple[bytes, bytes]
) -> None:
    db = Database(config.data_root)
    db.migrate()
    library = Library(config, db)
    header, fragments = segments(pixels[0])
    assert len(fragments) == 4
    assert not list(library.root.glob("*.part"))
    captured = library.begin("synthetic", "Generated camera", header)
    # A fragment begun before the click is excluded.
    library.write(captured.id, fragments[0], time.monotonic() - 5)
    for fragment in fragments[1:]:
        library.write(captured.id, fragment, time.monotonic())
    library.active.pop(captured.id).handle.close()  # Simulate an interrupted process.
    recovered = Library(config, db)
    asyncio.run(recovered.recover())
    ready = recovered.get(captured.id)
    assert ready.state == "ready" and ready.kind == "recording"
    assert ready.duration_seconds is not None and 2.5 <= ready.duration_seconds <= 3.2
    assert ready.width == 320 and ready.height == 240
    assert recovered.media(ready.id)[0].is_file()
    assert asyncio.run(recovered.finish(ready.id)) == ready
    db.close()


def test_snapshot_is_decoded_persisted_and_not_an_event(
    config: Config, pixels: tuple[bytes, bytes]
) -> None:
    db = Database(config.data_root)
    db.migrate()
    library = Library(config, db)
    saved = asyncio.run(library.snapshot("synthetic", "Generated camera", pixels[1]))
    assert saved.state == "ready" and saved.kind == "snapshot"
    assert saved.duration_seconds is None and saved.width == 320 and saved.height == 240
    path, mime = library.media(saved.id)
    assert mime == "image/jpeg" and jpeg_size(path.read_bytes()) == (320, 240)
    assert library.listing().items == [saved]
    db.close()


def test_empty_or_invalid_recordings_fail_without_claiming_playback(config: Config) -> None:
    db = Database(config.data_root)
    db.migrate()
    library = Library(config, db)
    capture = library.begin("synthetic", "Generated", b"invalid")
    failed = asyncio.run(library.finish(capture.id))
    assert failed.state == "failed" and failed.safe_error
    with pytest.raises(ApiError):
        library.media(failed.id)
    db.close()


def test_recording_size_limit_is_a_failed_capture_not_a_playable_file(
    config: Config, pixels: tuple[bytes, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    import porchlight.library as module

    db = Database(config.data_root)
    db.migrate()
    library = Library(config, db)
    header, fragments = segments(pixels[0])
    capture = library.begin("synthetic", "Generated", header)
    monkeypatch.setattr(module, "MAX_RECORDING", len(header) + 1)
    library.write(capture.id, fragments[0], time.monotonic())
    assert library.get(capture.id).state == "failed"
    assert capture.id not in library.active
    with pytest.raises(ApiError):
        library.media(capture.id)
    db.close()


@pytest.mark.parametrize(
    "data",
    [b"not jpeg", b"x" * (MAX_SNAPSHOT + 1), b"\xff\xd8\xff\xc0\x00\x08\x08\xff\xff\xff\xff\x01"],
    ids=["invalid", "oversized", "oversized-dimensions"],
)
def test_invalid_or_oversized_snapshot_is_rejected_before_decode(data: bytes) -> None:
    with pytest.raises(ApiError):
        jpeg_size(data)


def test_capture_api_has_freshness_csrf_owner_and_media_boundaries(
    authenticated: tuple[TestClient, dict[str, str]], pixels: tuple[bytes, bytes]
) -> None:
    client, headers = authenticated
    actor = digest(client.cookies[COOKIE])
    current = Session(id=str(uuid4()), camera_id=str(uuid4()), actor=actor, camera_name="Generated")
    client.app.state.live.session = current
    route = f"/api/v1/live/{current.id}"
    assert client.post(route + "/record", headers={"Origin": headers["Origin"]}).status_code == 403
    assert client.post(route + "/record", headers=headers).status_code == 409
    current.attached, current.state, current.last_media = True, "receiving", time.monotonic()
    current.fragments.feed(segments(pixels[0])[0])
    result = client.post(route + "/record", headers=headers)
    assert result.status_code == 201 and result.json()["state"] == "recording"
    assert client.post(route + "/record", headers=headers).status_code == 409
    snapshot = client.post(
        route + "/snapshot", headers={**headers, "Content-Type": "image/jpeg"}, content=pixels[1]
    )
    assert snapshot.status_code == 201 and snapshot.json()["state"] == "ready"
    capture_id = snapshot.json()["id"]
    media = f"/api/v1/library/{capture_id}/media"
    assert client.get(media, headers={"Range": "bytes=0-15"}).status_code == 206
    assert client.head(media).status_code == 200
    assert (
        client.get(f"/api/v1/library/{capture_id}/thumbnail").headers["content-type"]
        == "image/jpeg"
    )
    current.actor = "other-session"
    assert (
        client.post(
            route + "/snapshot",
            headers={**headers, "Content-Type": "image/jpeg"},
            content=pixels[1],
        ).status_code
        == 404
    )
    current.actor = actor
    current.last_media = time.monotonic() - 6
    assert (
        client.post(
            route + "/snapshot",
            headers={**headers, "Content-Type": "image/jpeg"},
            content=pixels[1],
        ).status_code
        == 409
    )
    assert (
        client.post(
            route + "/snapshot",
            headers={**headers, "Content-Type": "image/jpeg"},
            content=b"x" * (MAX_SNAPSHOT + 1),
        ).status_code
        == 413
    )
    client.cookies.clear()
    assert client.get(media).status_code == 401
    assert client.head(media).status_code == 401
    assert client.get("/api/v1/library").status_code == 401


def test_library_pagination_and_source_containment(
    config: Config, pixels: tuple[bytes, bytes]
) -> None:
    db = Database(config.data_root)
    db.migrate()
    library = Library(config, db)
    with db.session() as session:
        for index in range(31):
            session.add(
                Capture(
                    id=str(uuid4()),
                    camera_id="fixture",
                    camera_name="Generated",
                    kind="snapshot",
                    state="failed",
                    saved_at=f"2026-10-07T00:00:{index:02d}Z",
                    bytes=0,
                    width=0,
                    height=0,
                    duration_seconds=None,
                    sha256=None,
                    safe_error="Synthetic failure",
                )
            )
        session.commit()
    first = library.listing()
    assert len(first.items) == 30 and first.next_cursor
    second = library.listing(first.next_cursor)
    assert len(second.items) == 1 and not second.next_cursor
    saved = asyncio.run(library.snapshot("fixture", "Generated", pixels[1]))
    library.path(saved.id, ".jpg").unlink()
    with pytest.raises(ApiError):
        library.media(saved.id)
    with pytest.raises(ApiError):
        library.path(saved.id, "/../../outside.jpg")
    db.close()
