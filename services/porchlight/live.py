from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from porchlight.api.contracts import ApiError, CaptureView, LiveSession, RelayTrustRequired
from porchlight.config import Config
from porchlight.ingestion.fragments import Fragments
from porchlight.library import Library
from porchlight.providers.base import LiveInput, LiveProvider


@dataclass
class Session:
    id: str
    camera_id: str
    actor: str
    created: float = field(default_factory=time.monotonic)
    expires: float = field(default_factory=lambda: time.time() + 90)
    touched: float = field(default_factory=time.monotonic)
    last_media: float | None = None
    state: Literal["starting", "receiving", "stalled", "ended", "failed"] = "starting"
    message: str = "Connecting to Blink…"
    bytes_received: int = 0
    certificate_sha256: str | None = None
    attached: bool = False
    queue: asyncio.Queue[bytes | None] = field(default_factory=lambda: asyncio.Queue(8))
    task: asyncio.Task[None] | None = None
    camera_name: str = "Camera"
    fragments: Fragments = field(default_factory=Fragments)
    recording_id: str | None = None
    last_snapshot: float = 0.0


class LiveViews:
    """One ephemeral, owner-triggered 90-second stream; no saved footage or automatic retries."""

    def __init__(self, config: Config, provider: LiveProvider, library: Library | None = None):
        self.config, self.provider = config, provider
        self.session: Session | None = None
        self.lock = asyncio.Lock()
        self.last_start = 0.0
        self.session_valid: Callable[[str], bool] = lambda _: True
        self.library = library

    async def start(self, camera_id: str, actor: str, camera_name: str = "Camera") -> LiveSession:
        async with self.lock:
            if self.session and (
                self.session.state not in {"ended", "failed"}
                or (self.session.task and not self.session.task.done())
            ):
                raise ApiError(409, "LIVE_BUSY", "A live session is already open. Close it first.")
            if time.monotonic() - self.last_start < 60:
                raise ApiError(429, "LIVE_COOLDOWN", "Wait a minute between live sessions.", True)
            if not self.config.tool_path("ffmpeg"):
                raise ApiError(409, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg before live view.")
            self.last_start = time.monotonic()
            current = Session(
                id=str(uuid4()), camera_id=camera_id, actor=actor, camera_name=camera_name
            )
            self.session = current
            current.task = asyncio.create_task(self.run(current))
            return self.view(current)

    def require(self, session_id: str, actor: str) -> Session:
        current = self.session
        if not current or current.id != session_id or current.actor != actor:
            raise ApiError(404, "LIVE_NOT_FOUND", "This live session is unavailable.")
        return current

    def view(self, current: Session) -> LiveSession:
        age = (
            None if current.last_media is None else round(time.monotonic() - current.last_media, 2)
        )
        state = (
            "stalled"
            if current.state == "receiving" and age is not None and age > 5
            else current.state
        )
        return LiveSession(
            id=current.id,
            camera_id=current.camera_id,
            state=state,
            message="Video has stopped arriving." if state == "stalled" else current.message,
            expires_at=datetime.fromtimestamp(current.expires, UTC).isoformat(),
            bytes_received=current.bytes_received,
            media_age_seconds=age,
            certificate_sha256=current.certificate_sha256,
            recording=self.library.get(current.recording_id)
            if self.library and current.recording_id
            else None,
        )

    def capture_ready(self, session_id: str, actor: str) -> Session:
        current = self.require(session_id, actor)
        if (
            not self.library
            or not self.session_valid(actor)
            or not current.attached
            or current.state != "receiving"
            or current.last_media is None
            or time.monotonic() - current.last_media > 5
        ):
            raise ApiError(409, "LIVE_NOT_FRESH", "Wait for fresh live video before capturing.")
        return current

    async def start_recording(self, session_id: str, actor: str) -> CaptureView:
        async with self.lock:
            current = self.capture_ready(session_id, actor)
            assert self.library
            if current.recording_id and self.library.get(current.recording_id).state in {
                "recording",
                "saving",
            }:
                raise ApiError(409, "RECORDING_ACTIVE", "A recording is already in progress.")
            if not current.fragments.initialized:
                raise ApiError(409, "LIVE_NOT_READY", "Wait for the live video to initialize.")
            result = self.library.begin(
                current.camera_id, current.camera_name, current.fragments.header
            )
            current.recording_id = result.id
            return result

    async def stop_recording(self, session_id: str, actor: str) -> CaptureView:
        async with self.lock:
            current = self.require(session_id, actor)
            if not self.library or not current.recording_id:
                raise ApiError(409, "RECORDING_NOT_STARTED", "No recording is in progress.")
            return await self.library.finish(current.recording_id)

    async def snapshot(self, session_id: str, actor: str, data: bytes) -> CaptureView:
        current = self.capture_ready(session_id, actor)
        if time.monotonic() - current.last_snapshot < 1:
            raise ApiError(429, "SNAPSHOT_COOLDOWN", "Wait a second between snapshots.", True, 1)
        current.last_snapshot = time.monotonic()
        assert self.library
        return await self.library.snapshot(current.camera_id, current.camera_name, data)

    def status(self, session_id: str, actor: str) -> LiveSession:
        return self.view(self.require(session_id, actor))

    def touch(self, session_id: str, actor: str) -> LiveSession:
        current = self.require(session_id, actor)
        current.touched = time.monotonic()
        return self.view(current)

    async def stop(self, session_id: str | None = None, actor: str | None = None) -> None:
        async with self.lock:
            current = self.session
            if session_id and actor:
                current = self.require(session_id, actor)
            if not current:
                return
            if current.task and not current.task.done():
                current.task.cancel()
                with suppress(asyncio.CancelledError):
                    await current.task
            if current.state != "failed":
                current.state, current.message = "ended", "Live view ended."

    async def media(self, current: Session) -> AsyncIterator[bytes]:
        try:
            while True:
                if not self.session_valid(current.actor):
                    break
                try:
                    chunk = await asyncio.wait_for(current.queue.get(), 30)
                except TimeoutError:
                    break
                if chunk is None:
                    break
                yield chunk
        finally:
            if self.session is current:
                await self.stop(current.id, current.actor)

    async def run(self, current: Session) -> None:
        source: LiveInput | None = None
        process: asyncio.subprocess.Process | None = None
        tasks: list[asyncio.Task[None]] = []
        try:
            async with asyncio.timeout(25):
                source = await self.provider.open_live(current.camera_id)
                executable = self.config.tool_path("ffmpeg")
                assert executable
                process = await asyncio.create_subprocess_exec(
                    executable,
                    "-v",
                    "error",
                    "-nostdin",
                    "-threads",
                    "2",
                    "-protocol_whitelist",
                    "pipe",
                    "-probesize",
                    "1000000",
                    "-analyzeduration",
                    "1000000",
                    "-f",
                    "mpegts",
                    "-i",
                    "pipe:0",
                    "-map",
                    "0:v:0",
                    "-an",
                    "-vf",
                    "scale=960:540:force_original_aspect_ratio=decrease:force_divisible_by=2",
                    "-c:v",
                    "libx264",
                    "-threads",
                    "2",
                    "-preset",
                    "veryfast",
                    "-tune",
                    "zerolatency",
                    "-profile:v",
                    "baseline",
                    "-level:v",
                    "3.0",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    "12",
                    "-g",
                    "12",
                    "-keyint_min",
                    "12",
                    "-sc_threshold",
                    "0",
                    "-bf",
                    "0",
                    "-b:v",
                    "1200k",
                    "-maxrate",
                    "1600k",
                    "-bufsize",
                    "2000k",
                    "-f",
                    "mp4",
                    "-movflags",
                    "frag_keyframe+empty_moov+default_base_moof",
                    "-flush_packets",
                    "1",
                    "pipe:1",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            assert source and process and process.stdin and process.stdout
            live_input, encoder = source, process

            async def input_video() -> None:
                assert encoder.stdin
                try:
                    while data := await live_input.read():
                        encoder.stdin.write(data)
                        await encoder.stdin.drain()
                finally:
                    encoder.stdin.close()

            async def output_video() -> None:
                assert encoder.stdout
                while data := await encoder.stdout.read(64 * 1024):
                    current.bytes_received += len(data)
                    if current.bytes_received > 32 * 1024**2:
                        raise ApiError(
                            409, "LIVE_LIMIT", "The live session reached its byte limit."
                        )
                    current.last_media = time.monotonic()
                    current.state, current.message = "receiving", "Video is arriving."
                    if self.library:
                        try:
                            fragments = current.fragments.feed(data)
                            if current.recording_id:
                                for started, fragment in fragments:
                                    self.library.write(current.recording_id, fragment, started)
                        except ValueError:
                            current.fragments = Fragments()
                            if current.recording_id:
                                self.library.fail(
                                    current.recording_id,
                                    "The live recording format could not be captured.",
                                )
                    await asyncio.wait_for(current.queue.put(data), 5)

            async def watchdog() -> None:
                while True:
                    await asyncio.sleep(1)
                    now = time.monotonic()
                    if time.time() >= current.expires:
                        return
                    if now - current.touched > 12 or not self.session_valid(current.actor):
                        return
                    if current.last_media is None and now - current.created > 25:
                        raise ApiError(503, "LIVE_NO_VIDEO", "No video arrived from the camera.")
                    if current.last_media is not None and now - current.last_media > 10:
                        raise ApiError(503, "LIVE_STALLED", "The live video stopped arriving.")

            tasks = [
                asyncio.create_task(input_video()),
                asyncio.create_task(output_video()),
                asyncio.create_task(watchdog()),
            ]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for completed in done:
                completed.result()
            if tasks[0] in done and tasks[1] not in done:
                await asyncio.wait_for(tasks[1], 5)  # Drain the encoder after upstream EOF.
            if current.bytes_received == 0:
                raise ApiError(503, "LIVE_NO_VIDEO", "No video arrived from the camera.")
            current.state, current.message = "ended", "Live view ended."
        except asyncio.CancelledError:
            current.state, current.message = "ended", "Live view ended."
            raise
        except RelayTrustRequired as error:
            current.state, current.message = "failed", error.message
            current.certificate_sha256 = error.fingerprint
        except ApiError as error:
            current.state, current.message = "failed", error.message
        except Exception:
            current.state, current.message = (
                "failed",
                "Live view could not complete. Try again later.",
            )
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError, Exception):
                    await task
            if source:
                with suppress(Exception):
                    await source.close()
            if process:
                if process.stdin:
                    process.stdin.close()
                if process.returncode is None:
                    with suppress(TimeoutError):
                        await asyncio.wait_for(process.wait(), 2)
                if process.returncode is None:
                    process.kill()  # Only this owned child; never an unrelated PID.
                    await process.wait()
            while current.queue.full():
                current.queue.get_nowait()
            current.queue.put_nowait(None)
            if self.library and current.recording_id:
                saving = asyncio.create_task(self.library.finish(current.recording_id))
                try:
                    await asyncio.shield(saving)
                except asyncio.CancelledError:
                    await saving
                    raise
