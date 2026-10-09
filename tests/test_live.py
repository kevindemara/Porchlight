import asyncio
import json
import ssl
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError, RelayTrustRequired
from porchlight.config import Config
from porchlight.ingestion.imports import run_tool
from porchlight.library import Library
from porchlight.live import LiveViews
from porchlight.providers.blink.live import BlinkLiveInput, VerifiedStream, relay_target
from porchlight.storage.database import Database


class GeneratedInput:
    def __init__(self, data: bytes):
        self.data, self.offset, self.closed = data, 0, False

    async def read(self) -> bytes:
        await asyncio.sleep(0.05)
        chunk = self.data[self.offset : self.offset + 1316]
        self.offset += len(chunk)
        return chunk

    async def close(self) -> None:
        self.closed = True


class GeneratedProvider:
    def __init__(self, source: GeneratedInput):
        self.source = source

    async def open_live(self, _: str) -> GeneratedInput:
        return self.source


@pytest.fixture
def generated_ts(config: Config, tmp_path: Path) -> bytes:
    executable = config.tool_path("ffmpeg")
    if not executable:
        pytest.skip("Install FFmpeg explicitly to exercise the live encoder")
    path = tmp_path / "generated.ts"
    subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=12:duration=3",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "ultrafast",
            "-g",
            "12",
            "-f",
            "mpegts",
            "-y",
            str(path),
        ],
        check=True,
        timeout=30,
    )
    return path.read_bytes()


@pytest.mark.parametrize(
    "url",
    [
        "immis://127.0.0.1:443/token?client_id=1",
        "immis://10.0.0.1:443/token?client_id=1",
        "immis://169.254.169.254:443/token?client_id=1",
        "immis://relay.example:443/token?client_id=1",
        "immis://blink.com.evil.test:443/token?client_id=1",
        "http://relay.blink.com:443/token?client_id=1",
        "immis://u:p@relay.blink.com:443/token?client_id=1",
        "immis://relay.blink.com:80/token?client_id=1",
        "immis://relay.blink.com:443/token?client_id=-1",
        "immis://relay.blink.com:443/token?client_id=4294967296",
    ],
)
def test_untrusted_live_relays_rejected(url: str) -> None:
    with pytest.raises(ApiError) as error:
        relay_target(url)
    assert error.value.code == "LIVE_RELAY_REJECTED"


def test_blink_relay_and_global_ip_are_supported() -> None:
    assert relay_target("immis://relay.blink.com:443/connection__stream?client_id=1") == (
        "relay.blink.com",
        443,
        False,
    )
    assert relay_target("immis://18.197.108.98:443/connection__stream?client_id=1")[2]


def test_packet_receiver_joins_partial_reads_and_bounds_payloads() -> None:
    async def run() -> None:
        stream = BlinkLiveInput(
            SimpleNamespace(serial="synthetic"),
            {
                "server": "immis://relay.blink.com:443/connection?client_id=1",
                "command_id": 1,
                "polling_interval": 2,
            },
            asyncio.Lock(),
        )
        reader = asyncio.StreamReader()
        stream.stream.target_reader = reader
        payload = b"\x47" + bytes(187)
        packet = b"\x00" + (1).to_bytes(4, "big") + len(payload).to_bytes(4, "big") + payload
        pending = asyncio.create_task(stream.read())
        for offset in range(0, len(packet), 7):
            reader.feed_data(packet[offset : offset + 7])
            await asyncio.sleep(0)
        assert await pending == payload
        reader.feed_data(b"\x00" + bytes(4) + (1024 * 1024 + 1).to_bytes(4, "big"))
        with pytest.raises(ApiError) as error:
            await stream.read()
        assert error.value.code == "LIVE_PACKET_REJECTED"

    asyncio.run(run())


def test_live_tls_verifies_chain_and_identity_before_sending_protocol_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[bytes] = []
    observed: list[tuple[ssl.VerifyMode, bool]] = []
    valid = False

    class Writer:
        def get_extra_info(self, _: str) -> Any:
            return SimpleNamespace(
                getpeercert=lambda: {
                    "subjectAltName": [("DNS", "*.blink.com" if valid else "evil.test")]
                }
            )

        def close(self) -> None:
            pass

        def write(self, data: bytes) -> None:
            written.append(data)

        async def drain(self) -> None:
            pass

    async def connect(*_: Any, **kwargs: Any) -> tuple[asyncio.StreamReader, Writer]:
        observed.append((kwargs["ssl"].verify_mode, kwargs["ssl"].check_hostname))
        return asyncio.StreamReader(), Writer()

    monkeypatch.setattr(asyncio, "open_connection", connect)

    async def run() -> None:
        nonlocal valid
        stream = VerifiedStream(
            SimpleNamespace(serial="synthetic"),
            {
                "server": "immis://18.197.108.98:443/connection?client_id=1",
                "command_id": 1,
                "polling_interval": 2,
            },
            {},
        )
        with pytest.raises(ApiError) as error:
            await stream.auth()
        assert error.value.code == "LIVE_TLS_REJECTED" and not written
        valid = True
        await stream.auth()
        assert written and all(mode == ssl.CERT_REQUIRED for mode, _ in observed)

    asyncio.run(run())


def test_generated_ts_is_encoded_to_browser_mp4_and_cleaned_up(
    config: Config, generated_ts: bytes
) -> None:
    source = GeneratedInput(generated_ts)

    async def run() -> None:
        manager = LiveViews(config, GeneratedProvider(source))
        view = await manager.start("synthetic", "owner-session")
        current = manager.require(view.id, "owner-session")
        with pytest.raises(ApiError):
            await manager.start("other", "other-session")
        with pytest.raises(ApiError):
            manager.status(view.id, "other-session")
        result = bytearray()
        current.attached = True
        async for chunk in manager.media(current):
            result.extend(chunk)
        assert b"ftyp" in result[:32] and b"moof" in result and b"mdat" in result
        assert current.state == "ended" and source.closed
        assert manager.status(view.id, "owner-session").bytes_received > 0
        assert manager.status(view.id, "owner-session").audio_status == "unavailable"
        next_source = GeneratedInput(generated_ts)
        manager.provider = GeneratedProvider(next_source)
        reconnect = await manager.start("synthetic", "owner-session")
        assert reconnect.id != view.id
        next_session = manager.require(reconnect.id, "owner-session")
        next_session.attached = True
        replay = bytearray()
        async for chunk in manager.media(next_session):
            replay.extend(chunk)
        assert b"ftyp" in replay[:32] and b"moof" in replay and b"mdat" in replay
        assert next_source.closed and next_session.state == "ended"

    asyncio.run(run())


def test_live_audio_is_encoded_and_retained_in_recordings(config: Config, tmp_path: Path) -> None:
    executable = config.tool_path("ffmpeg")
    probe = config.tool_path("ffprobe")
    if not executable or not probe:
        pytest.skip("Configure FFmpeg for synthetic audio verification")
    source_path = tmp_path / "generated-audio.ts"
    subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=12:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=4",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "ultrafast",
            "-g",
            "12",
            "-c:a",
            "aac",
            "-f",
            "mpegts",
            "-y",
            str(source_path),
        ],
        check=True,
        timeout=30,
    )
    db = Database(config.data_root)
    db.migrate()
    library = Library(config, db)

    async def run() -> None:
        manager = LiveViews(
            config, GeneratedProvider(GeneratedInput(source_path.read_bytes())), library
        )
        view = await manager.start("synthetic", "actor")
        current = manager.require(view.id, "actor")
        current.attached = True
        capture = None
        async for _ in manager.media(current):
            if capture is None and current.fragments.initialized:
                assert manager.view(current).audio_status == "available"
                capture = await manager.start_recording(view.id, "actor")
        assert capture
        saved = library.get(capture.id)
        assert saved.state == "ready"
        path, _ = library.media(saved.id)
        details = json.loads(
            await run_tool(
                probe,
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,codec_name,sample_rate,channels",
                "-of",
                "json",
                str(path),
            )
        )
        audio = [stream for stream in details["streams"] if stream["codec_type"] == "audio"]
        assert len(audio) == 1 and audio[0]["codec_name"] == "aac"
        assert audio[0]["sample_rate"] == "16000" and audio[0]["channels"] == 1
        pcm = await run_tool(
            executable,
            "-v",
            "error",
            "-nostdin",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-f",
            "s16le",
            "pipe:1",
        )
        assert len(pcm) > 16000
        # The generated tone survives encoding and capture finalization; silence would be all zero.
        assert any(pcm)

    try:
        asyncio.run(run())
    finally:
        db.close()


@pytest.mark.parametrize("status", [204, 404])
def test_stop_accepts_empty_body_and_logs_only_redacted_http_status(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, status: int
) -> None:
    released: list[bool] = []
    camera = SimpleNamespace(
        serial="synthetic-serial",
        network_id=1,
        sync=SimpleNamespace(
            blink=SimpleNamespace(urls=SimpleNamespace(base_url="https://rest.synthetic.blink.com"))
        ),
    )

    async def post(blink: Any, url: str, **kwargs: Any) -> Any:
        assert blink is camera.sync.blink
        assert url == "https://rest.synthetic.blink.com/network/1/command/2/done/"
        assert kwargs == {"json": False}
        return SimpleNamespace(status=status, release=lambda: released.append(True))

    monkeypatch.setattr("porchlight.providers.blink.live.api.http_post", post)
    caplog.set_level("INFO", logger="porchlight.providers.blink.live")

    async def run() -> None:
        source = BlinkLiveInput(
            camera,
            {
                "server": "immis://18.197.108.98:443/connection?client_id=1",
                "command_id": 2,
                "polling_interval": 2,
            },
            asyncio.Lock(),
        )
        await source.close()
        await source.close()  # Cleanup is idempotent, including the upstream request.
        assert source.closed

    asyncio.run(run())
    assert released == [True]
    assert len(caplog.records) == 1
    assert json.loads(caplog.records[0].message) == {
        "event": "blink_live_stop_response",
        "response_received": True,
        "http_status": status,
    }
    assert caplog.records[0].levelname == ("INFO" if status == 204 else "WARNING")


@pytest.mark.parametrize("trigger", ["stop", "upstream_eof"])
def test_reconnect_waits_for_previous_transport_cleanup(
    config: Config, generated_ts: bytes, trigger: str
) -> None:
    async def run() -> None:
        reading, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class ClosingInput(GeneratedInput):
            async def read(self) -> bytes:
                reading.set()
                return await super().read()

            async def close(self) -> None:
                closing.set()
                await asyncio.wait_for(release.wait(), 10)
                await super().close()

        first = ClosingInput(generated_ts if trigger == "stop" else b"")
        second = GeneratedInput(generated_ts)

        class Provider:
            calls = 0

            async def open_live(self, _: str) -> GeneratedInput:
                self.calls += 1
                assert self.calls == 1 or first.closed
                return first if self.calls == 1 else second

        provider = Provider()
        manager = LiveViews(config, provider)
        view = await manager.start("synthetic", "owner-session")
        current = manager.require(view.id, "owner-session")
        current.attached = True
        await asyncio.wait_for(reading.wait(), 5)
        if trigger == "upstream_eof":
            await asyncio.wait_for(closing.wait(), 5)
        stop = asyncio.create_task(manager.stop(view.id, "owner-session"))
        await asyncio.wait_for(closing.wait(), 5)
        restart = asyncio.create_task(manager.start("synthetic", "owner-session"))
        await asyncio.sleep(0.02)
        try:
            assert not restart.done() and provider.calls == 1
        finally:
            release.set()
        await asyncio.wait_for(stop, 5)
        reopened = await asyncio.wait_for(restart, 5)
        assert reopened.id != view.id and first.closed
        # A late old HTTP consumer must not stop the newer session.
        async for _ in manager.media(current):
            pass
        assert manager.session and manager.session.id == reopened.id
        manager.session.attached = True
        next_media = manager.media(manager.session)
        assert await asyncio.wait_for(anext(next_media), 5)
        assert provider.calls == 2
        await asyncio.wait_for(next_media.aclose(), 5)
        assert second.closed

    asyncio.run(run())


@pytest.mark.parametrize("termination", ["idle", "expired", "revoked"])
def test_live_watchdog_cleans_up_without_camera_restarts(config: Config, termination: str) -> None:
    class Waiting(GeneratedInput):
        async def read(self) -> bytes:
            await asyncio.sleep(60)
            return b""

    source = Waiting(b"")

    async def run() -> None:
        manager = LiveViews(config, GeneratedProvider(source))
        view = await manager.start("synthetic", "actor")
        current = manager.require(view.id, "actor")
        if termination == "idle":
            current.touched = time.monotonic() - 20
        elif termination == "expired":
            current.expires = time.time() - 1
        else:
            manager.session_valid = lambda _: False
        assert current.task
        await asyncio.wait_for(current.task, 8)
        assert source.closed
        assert current.state in {"ended", "failed"}

    asyncio.run(run())


@pytest.mark.parametrize("termination", ["eof", "stop"])
def test_live_recording_saves_on_end_or_stop_without_a_second_camera_connection(
    config: Config, generated_ts: bytes, termination: str
) -> None:
    db = Database(config.data_root)
    db.migrate()
    library = Library(config, db)
    source = GeneratedInput(generated_ts)

    async def run() -> None:
        manager = LiveViews(config, GeneratedProvider(source), library)
        view = await manager.start("synthetic", "actor", "Generated camera")
        current = manager.require(view.id, "actor")
        current.attached = True
        capture_id = None
        async for _ in manager.media(current):
            if capture_id is None and current.fragments.initialized:
                capture_id = (await manager.start_recording(view.id, "actor")).id
            elif capture_id and termination == "stop":
                writer = library.active.get(capture_id)
                if writer and writer.bytes > len(current.fragments.header) + 100:
                    await manager.stop(view.id, "actor")
                    break
        assert capture_id
        saved = library.get(capture_id)
        assert saved.state == "ready" and saved.duration_seconds and saved.bytes > 100
        assert source.closed
        assert manager.view(current).recording == saved

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_live_api_requires_auth_csrf_and_session_ownership(
    authenticated: tuple[TestClient, dict[str, str]], generated_ts: bytes
) -> None:
    client, headers = authenticated
    camera_id = str(uuid4())
    client.app.state.blink.live_cameras = {camera_id: {}}
    source = GeneratedInput(generated_ts)
    client.app.state.live.provider = GeneratedProvider(source)
    assert (
        client.post(
            f"/api/v1/cameras/{camera_id}/live", headers={"Origin": headers["Origin"]}
        ).status_code
        == 403
    )
    view = client.post(f"/api/v1/cameras/{camera_id}/live", headers=headers).json()
    route = f"/api/v1/live/{view['id']}"
    assert client.post(route + "/heartbeat").status_code == 403
    assert client.get(route).status_code == 200
    assert client.get(route + "/media", headers={"Range": "bytes=0-10"}).status_code == 400
    response = client.get(route + "/media")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == 'video/mp4; codecs="avc1.42E01E"'
    assert b"moof" in response.content
    assert client.post(route + "/stop", headers=headers).status_code == 204
    client.cookies.clear()
    assert client.get(route + "/media").status_code == 401


def test_failed_stream_has_safe_status_and_no_automatic_retry(config: Config) -> None:
    class Rejected:
        calls = 0

        async def open_live(self, _: str) -> GeneratedInput:
            self.calls += 1
            raise ApiError(409, "LIVE_TLS_REJECTED", "The relay could not be verified.")

    provider = Rejected()

    async def run() -> None:
        manager = LiveViews(config, provider)
        view = await manager.start("synthetic", "actor")
        current = manager.require(view.id, "actor")
        assert current.task
        await current.task
        assert manager.status(view.id, "actor").state == "failed" and provider.calls == 1
        assert "verified" in manager.status(view.id, "actor").message

    asyncio.run(run())


def test_certificate_review_requires_explicit_csrf_protected_owner_approval(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    camera_id = str(uuid4())
    fingerprint = "a" * 64
    adapter = client.app.state.blink
    adapter.live_cameras = {camera_id: {}}
    adapter.pending_live_certificates = {fingerprint: "synthetic-public-certificate"}

    class Review:
        async def open_live(self, _: str) -> GeneratedInput:
            raise RelayTrustRequired(fingerprint, "synthetic-public-certificate")

    client.app.state.live.provider = Review()
    view = client.post(f"/api/v1/cameras/{camera_id}/live", headers=headers).json()
    route = f"/api/v1/live/{view['id']}"
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        status = client.get(route).json()
        if status["state"] == "failed":
            break
        time.sleep(0.02)
    assert status["certificate_sha256"] == fingerprint
    assert "synthetic-public-certificate" not in json.dumps(status)
    assert not adapter.live_certificates
    assert client.post(route + "/trust-certificate").status_code == 403
    assert not adapter.live_certificates
    assert client.post(route + "/trust-certificate", headers=headers).status_code == 204
    assert adapter.live_certificates == {fingerprint: "synthetic-public-certificate"}
    assert not adapter.pending_live_certificates
    assert client.post(route + "/trust-certificate", headers=headers).status_code == 409
    assert client.post("/api/v1/live/certificates/revoke").status_code == 403
    assert adapter.live_certificates
    assert client.post("/api/v1/live/certificates/revoke", headers=headers).status_code == 204
    assert not adapter.live_certificates
    client.cookies.clear()
    assert client.post(route + "/trust-certificate", headers=headers).status_code == 401


def test_self_signed_certificate_is_inspected_without_authentication_or_silent_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[bytes] = []
    calls = 0

    class Writer:
        def get_extra_info(self, _: str) -> Any:
            return SimpleNamespace(getpeercert=lambda **_: b"synthetic-public-DER")

        def close(self) -> None:
            pass

        async def wait_closed(self) -> None:
            pass

        def write(self, data: bytes) -> None:
            written.append(data)

    async def connect(*_: Any, **kwargs: Any) -> tuple[asyncio.StreamReader, Writer]:
        nonlocal calls
        calls += 1
        if calls == 1:
            assert kwargs["ssl"].verify_mode == ssl.CERT_REQUIRED
            error = ssl.SSLCertVerificationError()
            error.verify_code = 18
            raise error
        assert kwargs["ssl"].verify_mode == ssl.CERT_NONE  # Certificate inspection only.
        return asyncio.StreamReader(), Writer()

    monkeypatch.setattr(asyncio, "open_connection", connect)

    async def run() -> None:
        stream = VerifiedStream(
            SimpleNamespace(serial="synthetic"),
            {
                "server": "immis://18.197.108.98:443/connection?client_id=1",
                "command_id": 1,
                "polling_interval": 2,
            },
            {},
        )
        with pytest.raises(RelayTrustRequired) as error:
            await stream.auth()
        assert len(error.value.fingerprint) == 64
        assert not written and calls == 2 and not stream.certificates

    asyncio.run(run())
