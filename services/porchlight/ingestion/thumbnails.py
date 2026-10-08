from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.ingestion.imports import run_tool


class Thumbnails:
    """Private, bounded still previews from already archived recordings; no AI or Blink calls."""

    def __init__(self, config: Config):
        self.config = config
        self.root = config.data_root / "thumbnails"
        self.lock = asyncio.Lock()

    async def get(self, path: Path, asset_id: str, media_type: str = "video/mp4") -> bytes:
        path = path.resolve()
        if (
            not path.is_relative_to((self.config.data_root / "media").resolve())
            or not path.is_file()
        ):
            raise ApiError(404, "MEDIA_NOT_FOUND", "The saved recording is unavailable.")
        cached = (self.root / f"{asset_id}-v1.jpg").resolve()
        if not cached.is_relative_to(self.root.resolve()):
            raise ApiError(404, "MEDIA_NOT_FOUND", "The saved recording is unavailable.")
        try:
            async with asyncio.timeout(20), self.lock:
                if cached.is_file() and 0 < cached.stat().st_size <= 512 * 1024:
                    return cached.read_bytes()
                executable = self.config.tool_path("ffmpeg")
                if not executable:
                    raise ApiError(503, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg for previews.")
                image = await run_tool(
                    executable,
                    "-v",
                    "error",
                    "-nostdin",
                    "-threads",
                    "2",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-f",
                    "mjpeg" if media_type == "image/jpeg" else "mov",
                    "-i",
                    str(path),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=640:640:force_original_aspect_ratio=decrease",
                    "-c:v",
                    "mjpeg",
                    "-q:v",
                    "4",
                    "-f",
                    "image2pipe",
                    "pipe:1",
                    timeout=15,
                )
                if not image.startswith(b"\xff\xd8") or len(image) > 512 * 1024:
                    raise ApiError(422, "PREVIEW_UNAVAILABLE", "This preview could not be created.")
                self.root.mkdir(parents=True, exist_ok=True)
                temporary = self.root / f"{uuid4()}.part"
                try:
                    temporary.write_bytes(image)
                    os.replace(temporary, cached)
                finally:
                    temporary.unlink(missing_ok=True)
                return image
        except (TimeoutError, OSError) as exc:
            raise ApiError(
                503, "PREVIEW_UNAVAILABLE", "This preview is temporarily unavailable."
            ) from exc
