from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import portalocker
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.notifications import plan_notifications
from porchlight.retention import check_space
from porchlight.storage.database import Database
from porchlight.storage.models import Event, MediaAsset, Tombstone

MAX_BYTES = 256 * 1024 * 1024
MAX_IMAGE_BYTES = 32 * 1024 * 1024


def media_suffix(manifest: dict[str, Any]) -> str:
    media_type = manifest.get("media_type", "video/mp4")
    if media_type not in {"video/mp4", "image/jpeg"}:
        raise ApiError(422, "INVALID_MEDIA", "Choose an MP4 video or JPEG image.")
    return ".jpg" if media_type == "image/jpeg" else ".mp4"


async def run_tool(*args: str, timeout: int = 30) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except (TimeoutError, asyncio.CancelledError):
        process.kill()
        await process.communicate()
        raise
    if process.returncode != 0:
        raise ApiError(422, "INVALID_MEDIA", "This media file could not be decoded.")
    return output


async def inspect_mp4(path: Path, config: Config) -> dict[str, Any]:
    probe, ffmpeg = config.tool_path("ffprobe"), config.tool_path("ffmpeg")
    if not probe or not ffmpeg:
        raise ApiError(
            503, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg and ffprobe before importing clips."
        )
    with path.open("rb") as handle:
        signature = handle.read(32)
    if len(signature) < 12 or signature[4:8] != b"ftyp":
        raise ApiError(422, "INVALID_MEDIA", "Choose an MP4 video file.")
    try:
        output = await run_tool(
            probe,
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            "mov",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        )
        details = json.loads(output)
        video = next(s for s in details["streams"] if s.get("codec_type") == "video")
        duration = float(details["format"]["duration"])
        width, height = int(video["width"]), int(video["height"])
        if not 0 < duration <= 300 or not 0 < width <= 4096 or not 0 < height <= 4096:
            raise ValueError("Limits exceeded")
        await run_tool(
            ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            "mov",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-f",
            "null",
            "-",
        )
        return {"duration_seconds": duration, "width": width, "height": height}
    except (ValueError, KeyError, StopIteration, TimeoutError) as exc:
        raise ApiError(
            422, "INVALID_MEDIA", "Use a valid MP4 up to 5 minutes and 4096 pixels per edge."
        ) from exc


async def inspect_jpeg(path: Path, config: Config) -> dict[str, Any]:
    probe, ffmpeg = config.tool_path("ffprobe"), config.tool_path("ffmpeg")
    if not probe or not ffmpeg:
        raise ApiError(503, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg before importing images.")
    with path.open("rb") as handle:
        if handle.read(3) != b"\xff\xd8\xff":
            raise ApiError(422, "INVALID_MEDIA", "Choose a JPEG image.")
    try:
        details = json.loads(
            await run_tool(
                probe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-f",
                "mjpeg",
                "-show_entries",
                "stream=codec_type,width,height",
                "-of",
                "json",
                str(path),
            )
        )
        image = next(s for s in details["streams"] if s.get("codec_type") == "video")
        width, height = int(image["width"]), int(image["height"])
        if not 0 < width <= 4096 or not 0 < height <= 4096:
            raise ValueError("Limits exceeded")
        decoded = await run_tool(
            ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-threads",
            "2",
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            "mjpeg",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-frames:v",
            "2",
            "-vf",
            "scale=1:1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        )
        if len(decoded) != 3:
            raise ValueError("A single image is required")
        return {"duration_seconds": 0, "width": width, "height": height}
    except (ValueError, KeyError, StopIteration, TimeoutError) as exc:
        raise ApiError(
            422, "INVALID_MEDIA", "Use one JPEG image up to 4096 pixels per edge."
        ) from exc


class Importer:
    def __init__(self, config: Config, db: Database):
        self.config, self.db = config, db
        self.media = config.data_root / "media"
        self.scratch = config.data_root / "tmp"
        self.media.mkdir(parents=True, exist_ok=True)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.lock = asyncio.Lock()

    async def import_request(self, request: Request) -> str:
        if self.lock.locked():
            raise ApiError(409, "IMPORT_BUSY", "Another import is in progress.")
        async with self.lock:
            return await self._import(request)

    async def _import(self, request: Request) -> str:
        if not self.config.tool_path("ffmpeg") or not self.config.tool_path("ffprobe"):
            raise ApiError(
                503, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg and ffprobe before importing."
            )
        if request.headers.get("content-type", "").split(";")[0] not in {
            "video/mp4",
            "image/jpeg",
            "application/octet-stream",
        }:
            raise ApiError(415, "MEDIA_REQUIRED", "Choose an MP4 video or JPEG image.")
        image_import = request.headers.get("content-type", "").split(";")[0] == "image/jpeg"
        limit = MAX_IMAGE_BYTES if image_import else MAX_BYTES
        check_space(self.config, self.db, limit)
        captured_at: str | None = None
        supplied_time = request.headers.get("x-recorded-at")
        if supplied_time:
            try:
                timestamp = datetime.fromisoformat(supplied_time)
                if timestamp.tzinfo is None:
                    raise ValueError("Missing timezone")
                captured_at = timestamp.astimezone(UTC).isoformat()
            except ValueError as exc:
                raise ApiError(
                    422, "INVALID_TIMESTAMP", "Recording time needs an explicit timezone."
                ) from exc
        temporary = self.scratch / f"{uuid4()}.part"
        size, checksum = 0, hashlib.sha256()
        try:
            with temporary.open("xb") as handle:
                async for data in request.stream():
                    size += len(data)
                    if size > limit:
                        raise ApiError(
                            413,
                            "IMPORT_TOO_LARGE",
                            "Use a video under 256 MiB or image under 32 MiB.",
                        )
                    checksum.update(data)
                    handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            metadata = await (
                inspect_jpeg(temporary, self.config)
                if image_import
                else inspect_mp4(temporary, self.config)
            )
            sha = checksum.hexdigest()
            source_key = f"manual:{sha}:{captured_at or 'unknown'}"
            manifest = {
                "source_key": source_key,
                "sha256": sha,
                "bytes": size,
                "captured_at": captured_at,
                "discovered_at": datetime.now(UTC).isoformat(),
                "media_type": "image/jpeg" if image_import else "video/mp4",
                **metadata,
            }
            journal = self.scratch / f"{uuid4()}.import.json"
            with journal.open("x", encoding="utf-8") as handle:
                json.dump(manifest, handle)
                handle.flush()
                os.fsync(handle.fileno())
            event_id = self.commit_import(manifest, temporary)
            journal.unlink()
            return event_id
        finally:
            temporary.unlink(missing_ok=True)

    def commit_import(self, manifest: dict[str, Any], temporary: Path | None = None) -> str:
        # Share the short promotion/commit critical section with physical deletion.
        with portalocker.Lock(self.config.data_root / "media.lock", timeout=10):
            final = self.media / f"{manifest['sha256']}{media_suffix(manifest)}"
            if temporary is not None:
                os.replace(temporary, final)
            if not final.is_file():
                raise ApiError(404, "MEDIA_NOT_FOUND", "The saved recording is unavailable.")
            return self._commit_import(manifest)

    def _commit_import(self, manifest: dict[str, Any]) -> str:
        with self.db.session() as db:
            if (
                manifest.get("source_type") in {"blink_cloud", "blink_local"}
                and db.get(Tombstone, manifest["source_key"]) is not None
            ):
                raise ApiError(409, "SOURCE_DELETED_LOCALLY", "This recording was deleted locally.")
            existing = db.scalar(select(Event).where(Event.source_key == manifest["source_key"]))
            asset = db.scalar(select(MediaAsset).where(MediaAsset.sha256 == manifest["sha256"]))
            if asset is None:
                asset = MediaAsset(
                    id=str(uuid4()),
                    sha256=manifest["sha256"],
                    relative_path=f"media/{manifest['sha256']}{media_suffix(manifest)}",
                    media_type=manifest.get("media_type", "video/mp4"),
                    bytes=manifest["bytes"],
                    duration_seconds=manifest["duration_seconds"],
                    width=manifest["width"],
                    height=manifest["height"],
                )
                db.add(asset)
                db.flush()
            if existing:
                existing.media_id = asset.id
                db.commit()
                return existing.id
            event = Event(
                id=str(uuid4()),
                source_type=manifest.get("source_type", "manual_import"),
                source_key=manifest["source_key"],
                captured_at=manifest["captured_at"],
                discovered_at=manifest["discovered_at"],
                timestamp_quality=manifest.get(
                    "timestamp_quality", "owner_supplied" if manifest["captured_at"] else "unknown"
                ),
                camera_id=manifest.get("camera_id"),
                historical=manifest.get("historical") is True,
                media_id=asset.id,
                analysis_status="not_analyzed",
                summary=None,
                favourite=False,
                note="",
            )
            db.add(event)
            db.flush()
            plan_notifications(db, event)
            try:
                db.commit()
            except IntegrityError as exc:
                raise ApiError(
                    409, "IMPORT_CONFLICT", "This import is already being saved."
                ) from exc
            return event.id

    def recover(self) -> int:
        recovered = 0
        for journal in self.scratch.glob("*.import.json"):
            try:
                manifest = json.loads(journal.read_text(encoding="utf-8"))
                sha = str(manifest["sha256"])
                if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                    continue
                path = self.media / f"{sha}{media_suffix(manifest)}"
                if not path.is_file():
                    continue
                with path.open("rb") as handle:
                    actual_sha = hashlib.file_digest(handle, "sha256").hexdigest()
                if actual_sha == sha:
                    self.commit_import(manifest)
                    journal.unlink()
                    recovered += 1
            except (OSError, ValueError, KeyError, ApiError):
                continue
        # Partial files are never treated as playable; keep them for explicit later cleanup.
        return recovered
