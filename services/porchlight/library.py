from __future__ import annotations

import asyncio
import hashlib
import os
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Literal
from uuid import UUID, uuid4

from sqlalchemy import select

from porchlight.api.contracts import ApiError, CaptureList, CaptureView
from porchlight.config import Config
from porchlight.ingestion.imports import inspect_mp4, run_tool
from porchlight.retention import check_space
from porchlight.storage.database import Database
from porchlight.storage.models import Capture

MAX_RECORDING = 32 * 1024**2
MAX_SNAPSHOT = 2 * 1024**2


def jpeg_size(data: bytes) -> tuple[int, int]:
    """Reject oversized JPEG dimensions before handing pixels to the native decoder."""
    if len(data) > MAX_SNAPSHOT or not data.startswith(b"\xff\xd8"):
        raise ApiError(422, "INVALID_SNAPSHOT", "Use a valid JPEG snapshot.")
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 255:
            break
        while offset < len(data) and data[offset] == 255:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD9, 0xDA}:
            break
        length = int.from_bytes(data[offset : offset + 2], "big")
        if length < 2 or offset + length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2} and length >= 8:
            height = int.from_bytes(data[offset + 3 : offset + 5], "big")
            width = int.from_bytes(data[offset + 5 : offset + 7], "big")
            if 0 < width <= 4096 and 0 < height <= 4096 and width * height <= 4_194_304:
                return width, height
            break
        offset += length
    raise ApiError(422, "INVALID_SNAPSHOT", "This snapshot has unsupported dimensions.")


@dataclass
class Writer:
    handle: BinaryIO
    started: float
    bytes: int


class Library:
    """Explicit local captures; completed segments are recoverable after interruption."""

    def __init__(self, config: Config, db: Database):
        self.config, self.db = config, db
        self.root = config.data_root / "media/live-library"
        self.root.mkdir(parents=True, exist_ok=True)
        self.active: dict[str, Writer] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.snapshot_lock = asyncio.Lock()

    def path(self, capture_id: str, suffix: str) -> Path:
        path = (self.root / f"{UUID(capture_id)}{suffix}").resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_relative_to(
            (self.config.data_root / "media").resolve()
        ):
            raise ApiError(404, "CAPTURE_NOT_FOUND", "This capture is unavailable.")
        return path

    def get(self, capture_id: str) -> CaptureView:
        with self.db.session() as db:
            row = db.get(Capture, capture_id)
            if not row:
                raise ApiError(404, "CAPTURE_NOT_FOUND", "This capture is unavailable.")
            return CaptureView.model_validate(
                {key: getattr(row, key) for key in CaptureView.model_fields}
            )

    def listing(self, cursor: str | None = None) -> CaptureList:
        with self.db.session() as db:
            query = select(Capture)
            if cursor:
                previous = db.get(Capture, cursor)
                if not previous:
                    raise ApiError(422, "INVALID_CURSOR", "Reload the library.")
                query = query.where(
                    (Capture.saved_at < previous.saved_at)
                    | ((Capture.saved_at == previous.saved_at) & (Capture.id < previous.id))
                )
            rows = list(
                db.scalars(query.order_by(Capture.saved_at.desc(), Capture.id.desc()).limit(31))
            )
            return CaptureList(
                items=[self.get(row.id) for row in rows[:30]],
                next_cursor=rows[29].id if len(rows) > 30 else None,
            )

    def reserve(self) -> None:
        if not self.config.tool_path("ffmpeg") or not self.config.tool_path("ffprobe"):
            raise ApiError(503, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg before saving captures.")
        check_space(self.config, self.db, MAX_RECORDING)

    def create(
        self, camera_id: str, camera_name: str, kind: Literal["recording", "snapshot"]
    ) -> str:
        self.reserve()
        capture_id = str(uuid4())
        with self.db.session() as db:
            db.add(
                Capture(
                    id=capture_id,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    kind=kind,
                    state="recording" if kind == "recording" else "saving",
                    saved_at=datetime.now(UTC).isoformat(),
                    bytes=0,
                    width=0,
                    height=0,
                    duration_seconds=None,
                    sha256=None,
                    safe_error=None,
                )
            )
            db.commit()
        return capture_id

    def begin(self, camera_id: str, camera_name: str, header: bytes) -> CaptureView:
        capture_id = self.create(camera_id, camera_name, "recording")
        try:
            handle = self.path(capture_id, ".part").open("xb")
            self.active[capture_id] = Writer(handle, time.monotonic(), 0)
            self.write(capture_id, header)
        except OSError:
            self.fail(capture_id, "The recording could not be written to local storage.")
        return self.get(capture_id)

    def write(self, capture_id: str, data: bytes, fragment_started: float | None = None) -> None:
        writer = self.active.get(capture_id)
        if not writer or (fragment_started is not None and fragment_started < writer.started):
            return
        try:
            if writer.bytes + len(data) > MAX_RECORDING:
                raise OSError("Recording limit")
            writer.handle.write(data)
            writer.handle.flush()
            os.fsync(writer.handle.fileno())
            writer.bytes += len(data)
        except OSError:
            self.fail(capture_id, "The recording reached a storage limit or could not be written.")

    def fail(self, capture_id: str, reason: str) -> None:
        writer = self.active.pop(capture_id, None)
        if writer:
            with suppress(OSError):
                writer.handle.close()
        with self.db.session() as db:
            row = db.get(Capture, capture_id)
            if row:
                row.state, row.safe_error = "failed", reason
                db.commit()

    async def snapshot(self, camera_id: str, camera_name: str, data: bytes) -> CaptureView:
        jpeg_size(data)
        if self.snapshot_lock.locked():
            raise ApiError(409, "SNAPSHOT_BUSY", "A snapshot is already being saved.")
        async with self.snapshot_lock:
            capture_id = self.create(camera_id, camera_name, "snapshot")
            try:
                with self.path(capture_id, ".part").open("xb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError:
                self.fail(capture_id, "The snapshot could not be written to local storage.")
            return await self.finish(capture_id)

    async def finish(self, capture_id: str) -> CaptureView:
        lock = self.locks.setdefault(capture_id, asyncio.Lock())
        async with lock:
            current = self.get(capture_id)
            if current.state in {"ready", "failed"}:
                return current
            writer = self.active.pop(capture_id, None)
            if writer:
                writer.handle.close()
            with self.db.session() as db:
                row = db.get(Capture, capture_id)
                assert row
                row.state = "saving"
                db.commit()
            staged = self.path(capture_id, ".part")
            suffix = ".mp4" if current.kind == "recording" else ".jpg"
            destination = self.path(capture_id, suffix)
            temporary = self.path(capture_id, f".saving{suffix}")
            try:
                executable = self.config.tool_path("ffmpeg")
                if not executable:
                    raise ValueError("Media tools missing")
                if not destination.is_file():
                    if current.kind == "recording":
                        await run_tool(
                            executable,
                            "-v",
                            "error",
                            "-nostdin",
                            "-y",
                            "-protocol_whitelist",
                            "file,pipe",
                            "-f",
                            "mov",
                            "-i",
                            str(staged),
                            "-map",
                            "0:v:0",
                            "-an",
                            "-c:v",
                            "copy",
                            "-map_metadata",
                            "-1",
                            "-avoid_negative_ts",
                            "make_zero",
                            "-movflags",
                            "+faststart",
                            str(temporary),
                        )
                        await inspect_mp4(temporary, self.config)
                    else:
                        jpeg_size(staged.read_bytes())
                        await run_tool(
                            executable,
                            "-v",
                            "error",
                            "-nostdin",
                            "-y",
                            "-threads",
                            "2",
                            "-protocol_whitelist",
                            "file,pipe",
                            "-f",
                            "image2",
                            "-i",
                            str(staged),
                            "-frames:v",
                            "1",
                            "-map_metadata",
                            "-1",
                            "-c:v",
                            "mjpeg",
                            "-q:v",
                            "3",
                            "-update",
                            "1",
                            str(temporary),
                        )
                        jpeg_size(temporary.read_bytes())
                    with temporary.open("rb+") as handle:
                        os.fsync(handle.fileno())
                    os.replace(temporary, destination)
                if current.kind == "recording":
                    details = await inspect_mp4(destination, self.config)
                    duration: float | None = float(details["duration_seconds"])
                    width, height = int(details["width"]), int(details["height"])
                else:
                    width, height = jpeg_size(destination.read_bytes())
                    duration = None
                with destination.open("rb") as handle:
                    sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
                with self.db.session() as db:
                    row = db.get(Capture, capture_id)
                    assert row
                    row.state, row.safe_error = "ready", None
                    row.bytes, row.sha256 = destination.stat().st_size, sha256
                    row.width, row.height, row.duration_seconds = width, height, duration
                    db.commit()
                staged.unlink(missing_ok=True)
            except (ApiError, OSError, ValueError, TimeoutError):
                self.fail(
                    capture_id,
                    "This capture could not be saved. "
                    "A recording needs at least one complete video segment.",
                )
            finally:
                temporary.unlink(missing_ok=True)
            return self.get(capture_id)

    def media(self, capture_id: str) -> tuple[Path, str]:
        current = self.get(capture_id)
        suffix = ".mp4" if current.kind == "recording" else ".jpg"
        path = self.path(capture_id, suffix)
        if current.state != "ready" or not path.is_file():
            raise ApiError(404, "CAPTURE_NOT_FOUND", "This capture is not available for playback.")
        return path, "video/mp4" if current.kind == "recording" else "image/jpeg"

    async def recover(self) -> None:
        with self.db.session() as db:
            ids = list(
                db.scalars(select(Capture.id).where(Capture.state.in_(["recording", "saving"])))
            )
        for capture_id in ids:
            await self.finish(capture_id)
