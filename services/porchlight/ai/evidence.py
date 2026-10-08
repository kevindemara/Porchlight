"""Regenerate a private evidence frame and verify its exact accepted JPEG checksum."""

from __future__ import annotations

import asyncio
import hashlib

from sqlalchemy import select

from porchlight.ai.frames import EXTRACTION_VERSION, frame_image
from porchlight.ai.workloads import Workload
from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.storage.database import Database
from porchlight.storage.models import Analysis, Event, MediaAsset
from porchlight.storage.work import local_work


class Evidence:
    def __init__(self, config: Config, db: Database):
        self.config, self.db = config, db
        self.slots = asyncio.Semaphore(2)
        self.pending = 0

    async def get(self, event_id: str, revision: int, frame_id: str) -> bytes:
        with self.db.session() as db:
            analysis = db.scalar(
                select(Analysis).where(
                    Analysis.event_id == event_id,
                    Analysis.revision == revision,
                )
            )
            event = db.get(Event, event_id)
            asset = db.get(MediaAsset, event.media_id) if event else None
            frame = (
                next((f for f in analysis.frames if f.get("frame_id") == frame_id), None)
                if analysis
                else None
            )
            if not asset or not frame:
                raise ApiError(404, "EVIDENCE_NOT_FOUND", "This sampled image is unavailable.")
            if frame.get("extraction_version") != EXTRACTION_VERSION:
                raise ApiError(
                    409,
                    "EVIDENCE_VERSION_CHANGED",
                    "Use the sampled times to review this older analysis.",
                )
            path = (self.config.data_root / asset.relative_path).resolve()
            if (
                not path.is_relative_to((self.config.data_root / "media").resolve())
                or not path.is_file()
            ):
                raise ApiError(404, "MEDIA_NOT_FOUND", "The saved recording is unavailable.")
            offset = frame.get("offset_ms")
            workload: Workload = frame.get("workload", "balanced")
            if (
                type(offset) is not int
                or not 0 <= offset <= round(asset.duration_seconds * 1000)
                or workload not in {"light", "balanced"}
            ):
                raise ApiError(
                    409, "EVIDENCE_UNAVAILABLE", "This sampled image cannot be verified."
                )
            expected, media_type = frame.get("sha256"), asset.media_type
        if self.pending >= 12:
            raise ApiError(
                429,
                "EVIDENCE_BUSY",
                "Other sampled images are being prepared. Try again shortly.",
                True,
                2,
            )
        self.pending += 1
        try:
            async with asyncio.timeout(20), self.slots:
                image = await frame_image(path, offset, self.config, media_type, workload)
                if await local_work(lambda: hashlib.sha256(image).hexdigest()) != expected:
                    raise ApiError(
                        409,
                        "EVIDENCE_CHANGED",
                        "This image no longer matches the analysis. Review the original recording.",
                    )
                return image
        except (OSError, TimeoutError) as exc:
            raise ApiError(
                503, "EVIDENCE_UNAVAILABLE", "The sampled image is temporarily unavailable.", True
            ) from exc
        finally:
            self.pending -= 1
