from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.orm import Session

from porchlight.ai.frames import frame_image
from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.faces.contracts import (
    FaceApprovalResult,
    FaceApprovalSelection,
    FaceBox,
    FaceCandidate,
    FaceCandidates,
    FaceGallery,
    FaceReport,
    FaceRescan,
    FaceResult,
    FaceSelection,
    FaceState,
    FaceStatus,
    PersonProfile,
    SavedFacePerson,
)
from porchlight.faces.descriptions import FaceDescription, description_context
from porchlight.faces.detector import MANIFEST, POLICY, check_runtime, sample_offsets
from porchlight.faces.gallery import GalleryItem, group_faces, suggest_face
from porchlight.faces.people import People
from porchlight.faces.recognizer import MANIFEST as RECOGNIZER_MANIFEST
from porchlight.faces.recognizer import Recognizer, check_recognizer, feature_for_box, rank_profiles
from porchlight.storage.database import Database
from porchlight.storage.models import (
    Analysis,
    Event,
    FaceDetection,
    IntegrationState,
    Job,
    MediaAsset,
)

logger = logging.getLogger("porchlight")


def preserve_manual_labels(previous: FaceReport, updated: FaceReport) -> FaceReport:
    """Keep owner assignments when a rescan verifies the same frame and face."""
    old_frames = {frame.offset_ms: frame for frame in previous.frames}
    for frame in updated.frames:
        old = old_frames.get(frame.offset_ms)
        if old is None or old.sha256 != frame.sha256:
            continue
        used: set[int] = set()
        for prior in old.faces:
            if prior.profile_id is None or prior.match_score is not None:
                continue
            best_index, best_overlap = -1, 0.0
            for index, current in enumerate(frame.faces):
                if index in used:
                    continue
                intersection = max(
                    0, min(prior.x + prior.width, current.x + current.width)
                    - max(prior.x, current.x),
                ) * max(
                    0, min(prior.y + prior.height, current.y + current.height)
                    - max(prior.y, current.y),
                )
                union = prior.width * prior.height + current.width * current.height - intersection
                overlap = intersection / union if union > 0 else 0.0
                if overlap > best_overlap:
                    best_index, best_overlap = index, overlap
            if best_index >= 0 and best_overlap >= 0.7:
                face = frame.faces[best_index]
                frame.faces[best_index] = face.model_copy(
                    update={"profile_id": prior.profile_id, "match_score": None}
                )
                used.add(best_index)
    return updated


class FacePipeline:
    """Restart-safe optional worker, independent of ingestion and Qwen descriptions."""

    def __init__(self, config: Config, db: Database):
        self.config, self.db = config, db
        self.people = People(config.data_root)
        self.wake = asyncio.Event()
        self.gallery_lock = asyncio.Lock()
        self.gallery_cache: tuple[object, FaceGallery] | None = None
        with db.session() as session:
            for job in session.scalars(
                select(Job).where(Job.type == "face_detect", Job.status == "running")
            ):
                accepted = session.get(FaceDetection, job.payload["event_id"])
                job.status = "done" if accepted and accepted.job_id == job.id else "queued"
                job.lease_until = None
                job.available_at = min(job.available_at, time.time())
            session.commit()

    @staticmethod
    def _labeled_totals(session: Session) -> tuple[dict[str, int], dict[str, int]]:
        """Count all labels and owner-confirmed labels independently of gallery paging."""
        rows = session.execute(text("""
            SELECT json_extract(face.value, '$.profile_id') AS person_id,
                   COUNT(*),
                   SUM(CASE WHEN json_extract(face.value, '$.match_score') IS NULL
                            THEN 1 ELSE 0 END)
            FROM face_detections AS detection,
                 json_each(detection.report, '$.frames') AS frame,
                 json_each(frame.value, '$.faces') AS face
            WHERE json_extract(face.value, '$.profile_id') IS NOT NULL
            GROUP BY person_id
        """)).all()
        return (
            {str(person_id): int(count) for person_id, count, _ in rows},
            {str(person_id): int(confirmed) for person_id, _, confirmed in rows},
        )

    def ready(self) -> None:
        check_runtime(self.config.face_model)
        if not self.config.tool_path("ffmpeg"):
            raise ApiError(409, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg before face detection.")

    def control(self) -> dict[str, object]:
        with self.db.session() as session:
            row = session.get(IntegrationState, "face_detection")
            return dict(row.values) if row else {"enabled": False}

    def view(self) -> FaceStatus:
        ready, message = True, "Local face detection is ready."
        try:
            self.ready()
        except ApiError as exc:
            ready, message = False, exc.message
        recognition_ready = False
        if ready:
            try:
                check_recognizer(self.config.sface_model)
                recognition_ready = True
            except ApiError:
                pass
        try:
            count = len(self.people.list().people)
        except ApiError:
            count = 0
            recognition_ready = False
            message = "Face profiles need repair; detection remains available."
        with self.db.session() as session:
            counts = dict(
                session.execute(
                    select(Job.status, func.count())
                    .where(Job.type == "face_detect")
                    .group_by(Job.status)
                ).all()
            )
        return FaceStatus(
            ready=ready,
            enabled=bool(self.control().get("enabled")),
            message=message,
            queued=counts.get("queued", 0),
            running=counts.get("running", 0),
            completed=counts.get("done", 0),
            failed=counts.get("failed", 0),
            recognition_ready=recognition_ready,
            people_count=count,
            auto_enroll_enabled=bool(self.control().get("auto_enroll_enabled")),
        )

    def set_enabled(self, enabled: bool) -> FaceStatus:
        if enabled:
            self.ready()
        with self.db.session() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            row = session.get(IntegrationState, "face_detection")
            if row is None:
                row = IntegrationState(id="face_detection", values={})
                session.add(row)
            values = {**row.values, "enabled": enabled}
            if enabled and not row.values.get("enabled"):
                values["enabled_at"] = datetime.now(UTC).isoformat()
                values["enabled_rowid"] = int(
                    session.connection()
                    .exec_driver_sql("SELECT COALESCE(MAX(rowid), 0) FROM events")
                    .scalar_one()
                )
            row.values = values
            session.commit()
        self.wake.set()
        return self.view()

    def set_auto_enroll_enabled(self, enabled: bool) -> FaceStatus:
        if enabled:
            self.ready()
            check_recognizer(self.config.sface_model)
        with self.db.session() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            row = session.get(IntegrationState, "face_detection")
            if row is None:
                row = IntegrationState(id="face_detection", values={})
                session.add(row)
            row.values = {**row.values, "auto_enroll_enabled": enabled}
            session.commit()
        return self.view()

    def result(self, event_id: str) -> FaceResult:
        with self.db.session() as session:
            if not session.get(Event, event_id):
                raise ApiError(404, "EVENT_NOT_FOUND", "This recording is unavailable.")
            row = session.get(FaceDetection, event_id)
            job = session.scalar(
                select(Job)
                .where(Job.type == "face_detect", Job.payload["event_id"].as_string() == event_id)
                .order_by(Job.available_at.desc())
                .limit(1)
            )
            report = FaceReport.model_validate(row.report) if row else None
            matched_ids = (
                {
                    str(face.profile_id)
                    for frame in report.frames
                    for face in frame.faces
                    if face.profile_id
                }
                if report
                else set()
            )
            try:
                names = self.people.names() if matched_ids else {}
            except ApiError:
                names = {}
            return FaceResult(
                status=cast(FaceState, job.status) if job else "not_requested",
                report=report,
                created_at=row.created_at if row else None,
                elapsed_seconds=row.elapsed_seconds if row else None,
                message="Face detection failed. Playback and previous results remain available."
                if job and job.status == "failed"
                else None,
                people={key: value for key, value in names.items() if key in matched_ids},
            )

    def names_for_events(self, event_ids: list[str]) -> dict[str, list[str]]:
        """Resolve saved matches at read time so renames and removals stay current."""
        return {
            key: list(value.names)
            for key, value in self.description_contexts(event_ids).items()
            if value.names
        }

    def description_contexts(self, event_ids: list[str]) -> dict[str, FaceDescription]:
        """Batch lightweight report/analysis metadata; no media or inference on reads."""
        if not event_ids:
            return {}
        with self.db.session() as session:
            latest = (
                select(Analysis.event_id, func.max(Analysis.revision).label("revision"))
                .where(Analysis.event_id.in_(event_ids))
                .group_by(Analysis.event_id)
                .subquery()
            )
            rows = session.execute(
                select(FaceDetection, Analysis)
                .outerjoin(latest, FaceDetection.event_id == latest.c.event_id)
                .outerjoin(
                    Analysis,
                    (Analysis.event_id == latest.c.event_id)
                    & (Analysis.revision == latest.c.revision),
                )
                .where(FaceDetection.event_id.in_(event_ids))
            ).all()
        if not rows:
            return {}
        try:
            names = self.people.names()
        except ApiError:
            return {}
        found: dict[str, FaceDescription] = {}
        for row, analysis in rows:
            report = FaceReport.model_validate(row.report)
            person_count = sum(
                entity.get("category") == "person"
                for entity in analysis.observation.get("entities", [])
            ) if analysis else 0
            found[row.event_id] = description_context(report, names, person_count)
        return found

    def candidates(self) -> FaceCandidates:
        faces: list[FaceCandidate] = []
        with self.db.session() as session:
            records = session.execute(
                select(FaceDetection, Event)
                .join(Event, FaceDetection.event_id == Event.id)
                .order_by(FaceDetection.created_at.desc())
                .limit(25)
            ).all()
            for detection, event in records:
                if not event.media_id:
                    continue
                report = FaceReport.model_validate(detection.report)
                for frame in report.frames:
                    for index, box in enumerate(frame.faces):
                        faces.append(
                            FaceCandidate(
                                event_id=UUID(event.id),
                                captured_at=event.captured_at or event.discovered_at,
                                frame_sha256=frame.sha256,
                                offset_ms=frame.offset_ms,
                                face_index=index,
                                width=frame.width,
                                height=frame.height,
                                box=box,
                            )
                        )
                        if len(faces) >= 50:
                            return FaceCandidates(faces=faces)
        return FaceCandidates(faces=faces)

    async def gallery(self, offset: int = 0) -> FaceGallery:
        """Build one private review page ordered by recording time, not scan time."""
        with self.db.session() as session:
            total = session.scalar(select(func.count()).select_from(FaceDetection)) or 0
            labeled_totals, confirmed_totals = self._labeled_totals(session)
            rows = session.execute(
                select(FaceDetection, Event)
                .join(Event, FaceDetection.event_id == Event.id)
                .order_by(
                    func.coalesce(Event.captured_at, Event.discovered_at).desc(),
                    Event.id.desc(),
                )
                .offset(offset)
                .limit(20)
            ).all()
        try:
            profiles = self.people.vectors()
            names = self.people.names()
            profile_state = tuple(
                sorted(
                    (str(person.id), person.name, person.samples)
                    for person in self.people.list().people
                )
            )
        except ApiError:
            profiles, names, profile_state = {}, {}, ()
        signature = (
            offset,
            total,
            tuple((row.event_id, row.job_id) for row, _ in rows),
            profile_state,
        )
        async with self.gallery_lock:
            if self.gallery_cache and self.gallery_cache[0] == signature:
                return self.gallery_cache[1]
            saved_people = self._saved_people(names)
            batches: list[list[FaceCandidate]] = []
            for detection, event in rows:
                report = FaceReport.model_validate(detection.report)
                faces = [
                    FaceCandidate(
                        event_id=UUID(event.id),
                        captured_at=event.captured_at or event.discovered_at,
                        frame_sha256=frame.sha256,
                        offset_ms=frame.offset_ms,
                        face_index=index,
                        width=frame.width,
                        height=frame.height,
                        box=box,
                    )
                    for frame in report.frames
                    for index, box in enumerate(frame.faces)
                ]
                faces.sort(
                    key=lambda item: (
                        not item.box.small and not item.box.low_sharpness,
                        min(item.box.width, item.box.height),
                        item.box.score,
                    ),
                    reverse=True,
                )
                batches.append(faces)
            # Spread the bounded review budget across recordings before taking
            # another face from the same clip. This keeps less frequent visitors
            # visible without dropping useful repeat samples when the set is small.
            candidates: list[FaceCandidate] = []
            while len(candidates) < 300 and any(batches):
                for batch in batches:
                    if batch and len(candidates) < 300:
                        candidates.append(batch.pop(0))
            omitted = sum(len(batch) for batch in batches)
            frame_cache: dict[tuple[str, int], bytes] = {}
            try:
                recognizer: Recognizer | None = await asyncio.to_thread(
                    Recognizer, self.config.sface_model
                )
            except Exception:
                recognizer = None
            items: list[GalleryItem] = []
            for face in candidates:
                feature: tuple[float, ...] | None = None
                key = str(face.event_id), face.offset_ms
                try:
                    if key not in frame_cache:
                        frame_cache[key] = await self.sample_frame(*key)
                    feature = await asyncio.to_thread(
                        feature_for_box,
                        frame_cache[key],
                        self.config.face_model,
                        self.config.sface_model,
                        face.box,
                        recognizer,
                    )
                except Exception:
                    pass  # The saved detection remains reviewable without a vector.
                items.append(GalleryItem(face, feature))
            suggestions = [
                suggestion for item in items
                if (suggestion := suggest_face(item, profiles, names)) is not None
            ]
            suggested = {
                (item.face.event_id, item.face.offset_ms, item.face.face_index)
                for item in suggestions
            }
            gallery = FaceGallery(
                groups=group_faces([
                    item for item in items
                    if (item.face.event_id, item.face.offset_ms, item.face.face_index)
                    not in suggested
                ], profiles, names),
                saved_people=saved_people,
                suggestions=suggestions,
                labeled_totals={
                    key: count for key, count in labeled_totals.items() if key in names
                },
                confirmed_totals={
                    key: count for key, count in confirmed_totals.items() if key in names
                },
                recordings_reviewed=len(rows),
                total_recordings=total,
                next_offset=offset + len(rows) if offset + len(rows) < total else None,
                omitted_faces=omitted,
            )
            self.gallery_cache = signature, gallery
            return gallery

    def _saved_people(self, names: dict[str, str]) -> list[SavedFacePerson]:
        """Find representative saved labels for every profile without loading media."""
        samples: dict[str, list[FaceCandidate]] = {person_id: [] for person_id in names}
        if not samples:
            return []
        with self.db.session() as session:
            rows = session.execute(
                select(FaceDetection, Event)
                .join(Event, FaceDetection.event_id == Event.id)
                .order_by(
                    func.coalesce(Event.captured_at, Event.discovered_at).desc(),
                    Event.id.desc(),
                )
            ).all()
        for detection, event in rows:
            report = FaceReport.model_validate(detection.report)
            for frame in report.frames:
                for index, box in enumerate(frame.faces):
                    person_id = str(box.profile_id) if box.profile_id else None
                    if person_id is None or person_id not in samples:
                        continue
                    candidate = FaceCandidate(
                        event_id=UUID(event.id),
                        captured_at=event.captured_at or event.discovered_at,
                        frame_sha256=frame.sha256,
                        offset_ms=frame.offset_ms,
                        face_index=index,
                        width=frame.width,
                        height=frame.height,
                        box=box,
                    )
                    choices = samples[person_id]
                    choices.append(candidate)
                    choices.sort(key=lambda item: (
                        not item.box.small and not item.box.low_sharpness,
                        min(item.box.width, item.box.height),
                        item.box.score,
                    ), reverse=True)
                    del choices[3:]
        return [
            SavedFacePerson(person_id=UUID(person_id), name=name, samples=samples[person_id])
            for person_id, name in names.items()
        ]

    async def thumbnail(self, event_id: str, offset_ms: int, face_index: int) -> bytes:
        jpeg = await self.sample_frame(event_id, offset_ms)
        with self.db.session() as session:
            row = session.get(FaceDetection, event_id)
            report = FaceReport.model_validate(row.report) if row else None
            frame = next(
                (item for item in report.frames if item.offset_ms == offset_ms), None
            ) if report else None
            if frame is None or face_index >= len(frame.faces):
                raise ApiError(404, "FACE_SAMPLE_NOT_FOUND", "This face sample is unavailable.")
            box = frame.faces[face_index]

        def crop() -> bytes:
            import cv2
            import numpy as np

            image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ApiError(422, "FACE_SAMPLE_INVALID", "This face sample cannot be shown.")
            side = round(max(box.width, box.height) * 1.8)
            center_x, center_y = box.x + box.width / 2, box.y + box.height / 2
            left = max(0, round(center_x - side / 2))
            top = max(0, round(center_y - side / 2))
            right = min(image.shape[1], round(center_x + side / 2))
            bottom = min(image.shape[0], round(center_y + side / 2))
            clipped = image[top:bottom, left:right]
            if clipped.size == 0:
                raise ApiError(422, "FACE_SAMPLE_INVALID", "This face sample cannot be shown.")
            if max(clipped.shape[:2]) > 400:
                scale = 400 / max(clipped.shape[:2])
                clipped = cv2.resize(clipped, None, fx=scale, fy=scale)
            ok, encoded = cv2.imencode(".jpg", clipped, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if not ok:
                raise ApiError(422, "FACE_SAMPLE_INVALID", "This face sample cannot be shown.")
            return bytes(encoded)

        return await asyncio.to_thread(crop)

    def rescan_recent(self) -> FaceRescan:
        """Queue the newest 20 saved videos as explicit, retryable face scans."""
        self.ready()
        with self.db.session() as session:
            ids = list(
                session.scalars(
                    select(Event.id)
                    .join(MediaAsset, Event.media_id == MediaAsset.id)
                    .where(MediaAsset.media_type == "video/mp4")
                    .order_by(func.coalesce(Event.captured_at, Event.discovered_at).desc())
                    .limit(20)
                )
            )
        queued = running = 0
        for event_id in ids:
            try:
                result = self.enqueue(event_id, reanalyze=True)
            except ApiError as exc:
                if exc.code == "FACE_QUEUE_FULL":
                    break
                raise
            if result.status == "running":
                running += 1
            elif result.status == "queued":
                queued += 1
        return FaceRescan(requested=len(ids), queued=queued, already_running=running)

    async def sample_frame(self, event_id: str, offset_ms: int) -> bytes:
        with self.db.session() as session:
            detection = session.get(FaceDetection, event_id)
            event = session.get(Event, event_id)
            asset = session.get(MediaAsset, event.media_id) if event and event.media_id else None
            if not detection or not asset:
                raise ApiError(404, "FACE_SAMPLE_NOT_FOUND", "This face sample is unavailable.")
            report = FaceReport.model_validate(detection.report)
            frame = next((item for item in report.frames if item.offset_ms == offset_ms), None)
            if frame is None:
                raise ApiError(404, "FACE_SAMPLE_NOT_FOUND", "This face sample is unavailable.")
            path = (self.config.data_root / asset.relative_path).resolve()
            if (
                not path.is_relative_to((self.config.data_root / "media").resolve())
                or not path.is_file()
            ):
                raise ApiError(404, "MEDIA_NOT_FOUND", "This recording is unavailable.")
            media_type = asset.media_type
        jpeg = await frame_image(path, offset_ms, self.config, media_type, "balanced")
        if hashlib.sha256(jpeg).hexdigest() != frame.sha256:
            raise ApiError(
                409, "FACE_SAMPLE_CHANGED", "The sampled recording changed; detect faces again."
            )
        return jpeg

    async def enroll(
        self,
        event_id: str,
        offset_ms: int,
        face_index: int,
        name: str | None,
        person_id: UUID | None = None,
    ) -> PersonProfile:
        return await self.enroll_many(
            [FaceSelection(event_id=UUID(event_id), offset_ms=offset_ms, face_index=face_index)],
            name,
            person_id,
        )

    async def enroll_many(
        self,
        samples: list[FaceSelection],
        name: str | None,
        person_id: UUID | None = None,
    ) -> PersonProfile:
        if not 1 <= len(samples) <= 12:
            raise ApiError(422, "FACE_SAMPLES_INVALID", "Select 1 to 12 faces at a time.")
        check_recognizer(self.config.sface_model)
        selected: list[tuple[FaceSelection, FaceBox, str]] = []
        with self.db.session() as session:
            for sample in samples:
                detection = session.get(FaceDetection, str(sample.event_id))
                if not detection:
                    raise ApiError(
                        404, "FACE_SAMPLE_NOT_FOUND", "Detect faces in this recording first."
                    )
                report = FaceReport.model_validate(detection.report)
                frame = next(
                    (item for item in report.frames if item.offset_ms == sample.offset_ms), None
                )
                if frame is None or sample.face_index >= len(frame.faces):
                    raise ApiError(404, "FACE_SAMPLE_NOT_FOUND", "This face sample is unavailable.")
                selected.append((sample, frame.faces[sample.face_index], frame.sha256))
        features: list[tuple[float, ...]] = []
        frame_cache: dict[tuple[str, int], bytes] = {}
        for index, (sample, box, _) in enumerate(selected, start=1):
            key = str(sample.event_id), sample.offset_ms
            if key not in frame_cache:
                frame_cache[key] = await self.sample_frame(*key)
            try:
                features.append(await asyncio.wait_for(
                    asyncio.to_thread(
                        feature_for_box, frame_cache[key], self.config.face_model,
                        self.config.sface_model, box,
                    ),
                    30,
                ))
            except (ValueError, TimeoutError) as exc:
                raise ApiError(
                    422, "FACE_ENROLLMENT_FAILED",
                    f"Could not extract face {index} of {len(samples)}. Try a clearer sample.",
                ) from exc
        if person_id is not None:
            profile = self.people.add_samples(person_id, features)
        elif name is not None:
            profile = self.people.create_samples(name, features)
        else:
            raise ApiError(422, "FACE_TARGET_REQUIRED", "Choose a name or saved person.")
        # Label the reviewed sample immediately; the next detection pass may add
        # model matches in other frames or clips independently of this action.
        with self.db.session() as session:
            for event_id in {str(item.event_id) for item in samples}:
                current = session.get(FaceDetection, event_id)
                if not current:
                    continue
                saved = FaceReport.model_validate(current.report)
                changed = False
                for sample, box, digest in selected:
                    if str(sample.event_id) != event_id:
                        continue
                    frame = next(
                        (item for item in saved.frames if item.offset_ms == sample.offset_ms),
                        None,
                    )
                    if (
                        frame and frame.sha256 == digest
                        and sample.face_index < len(frame.faces)
                        and frame.faces[sample.face_index] == box
                    ):
                        frame.faces[sample.face_index] = box.model_copy(
                            update={"profile_id": profile.id, "match_score": None}
                        )
                        changed = True
                if changed:
                    current.report = saved.model_dump(mode="json")
            session.commit()
        self.wake.set()
        return profile

    def approve_suggestions(
        self, person_id: UUID, faces: list[FaceApprovalSelection]
    ) -> FaceApprovalResult:
        """Owner-label reviewed boxes atomically, without changing SFace templates."""
        if not any(person.id == person_id for person in self.people.list().people):
            raise ApiError(404, "FACE_PERSON_NOT_FOUND", "This person is unavailable.")
        by_event: dict[str, list[FaceApprovalSelection]] = {}
        for face in faces:
            by_event.setdefault(str(face.event_id), []).append(face)
        with self.db.session() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            reports: dict[str, tuple[FaceDetection, FaceReport]] = {}
            for event_id, selections in by_event.items():
                row = session.get(FaceDetection, event_id)
                if row is None:
                    raise ApiError(
                        409, "FACE_REVIEW_STALE",
                        "A recording changed. Refresh the suggestions.",
                    )
                report = FaceReport.model_validate(row.report)
                for selection in selections:
                    frame = next(
                        (
                            frame for frame in report.frames
                            if frame.offset_ms == selection.offset_ms
                        ),
                        None,
                    )
                    if (
                        frame is None or frame.sha256 != selection.frame_sha256
                        or selection.face_index >= len(frame.faces)
                        or frame.faces[selection.face_index] != selection.box
                        or selection.box.profile_id is not None
                    ):
                        raise ApiError(
                            409, "FACE_REVIEW_STALE", "A face changed. Refresh the suggestions."
                        )
                    frame.faces[selection.face_index] = selection.box.model_copy(
                        update={"profile_id": person_id, "match_score": None}
                    )
                reports[event_id] = row, report
            for row, report in reports.values():
                row.report = report.model_dump(mode="json")
            session.flush()
            labeled_totals, confirmed_totals = self._labeled_totals(session)
            total_labeled = labeled_totals.get(str(person_id), 0)
            total_confirmed = confirmed_totals.get(str(person_id), 0)
            session.commit()
        self.gallery_cache = None
        return FaceApprovalResult(
            labeled=len(faces), total_labeled=total_labeled,
            total_confirmed=total_confirmed,
        )

    def enqueue(
        self, event_id: str, *, automatic: bool = False, reanalyze: bool = False
    ) -> FaceResult:
        self.ready()
        with self.db.session() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            event = session.get(Event, event_id)
            if not event or not event.media_id:
                raise ApiError(404, "EVENT_NOT_FOUND", "This recording is unavailable.")
            if automatic and event.historical:
                raise ApiError(
                    409, "FACE_HISTORY_MANUAL", "Detect faces in older imports manually."
                )
            key = f"faces:{event_id}:{POLICY}:{MANIFEST['sha256']}"
            jobs = list(
                session.scalars(
                    select(Job).where(
                        Job.type == "face_detect", Job.payload["event_id"].as_string() == event_id
                    )
                )
            )
            active = next((j for j in jobs if j.status in {"running", "queued"}), None)
            if active:
                if not automatic and active.status == "queued":
                    active.payload = {**active.payload, "automatic": False}
                    session.commit()
            elif not reanalyze and any(
                j.status == "done" and j.dedup_key.startswith(key) for j in jobs
            ):
                pass
            else:
                count = (
                    session.scalar(
                        select(func.count())
                        .select_from(Job)
                        .where(Job.type == "face_detect", Job.status.in_(["running", "queued"]))
                    )
                    or 0
                )
                if count >= 30:
                    raise ApiError(
                        409, "FACE_QUEUE_FULL", "The face detection queue is full. Try later."
                    )
                # Explicit retries get a new job; automatic scheduling bounds failed retries.
                session.add(
                    Job(
                        id=str(uuid4()),
                        type="face_detect",
                        dedup_key=f"{key}:{uuid4()}",
                        payload={
                            "event_id": event_id,
                            "automatic": automatic,
                            "policy": POLICY,
                            "model_sha256": MANIFEST["sha256"],
                        },
                        status="queued",
                        attempt=0,
                        available_at=time.time(),
                        lease_until=None,
                        safe_error=None,
                    )
                )
                session.commit()
        self.wake.set()
        return self.result(event_id)

    def schedule(self) -> None:
        control = self.control()
        since = control.get("enabled_at")
        if not control.get("enabled") or not isinstance(since, str):
            return
        watermark = control.get("enabled_rowid")
        new_event = (
            literal_column("events.rowid") > watermark
            if isinstance(watermark, int)
            else Event.discovered_at >= since
        )
        self.ready()
        recent = datetime.fromtimestamp(time.time() - 86400, UTC).isoformat()
        with self.db.session() as session:
            known = select(Job.payload["event_id"].as_string()).where(Job.type == "face_detect")
            ids = list(
                session.scalars(
                    select(Event.id)
                    .where(
                        new_event,
                        Event.captured_at >= recent,
                        Event.historical.is_(False),
                        Event.media_id.is_not(None),
                        Event.source_type.in_(["blink_cloud", "blink_local"]),
                        Event.id.not_in(known),
                    )
                    .order_by(Event.captured_at.desc())
                    .limit(30)
                )
            )
        for event_id in ids:
            try:
                self.enqueue(event_id, automatic=True)
            except ApiError as exc:
                if exc.code == "FACE_QUEUE_FULL":
                    break
                raise

    def claim(self) -> Job | None:
        enabled = bool(self.control().get("enabled"))
        with self.db.session() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            for job in session.scalars(
                select(Job)
                .where(
                    Job.type == "face_detect",
                    Job.status == "queued",
                    Job.available_at <= time.time(),
                )
                .order_by(Job.available_at)
            ):
                if job.payload.get("automatic"):
                    if not enabled:
                        continue
                    event = session.get(Event, job.payload["event_id"])
                    recent = datetime.fromtimestamp(time.time() - 86400, UTC).isoformat()
                    if (
                        not event
                        or event.historical
                        or not event.captured_at
                        or event.captured_at < recent
                    ):
                        job.status, job.safe_error = "expired", "FACE_BACKFILL_EXPIRED"
                        continue
                job.status, job.lease_until = "running", time.time() + 240
                job.attempt += 1
                session.commit()
                return job
            session.commit()
        return None

    async def detect(self, event_id: str) -> FaceReport:
        self.ready()
        with self.db.session() as session:
            event = session.get(Event, event_id)
            asset = session.get(MediaAsset, event.media_id) if event else None
            if not asset:
                raise ApiError(404, "MEDIA_NOT_FOUND", "This recording is unavailable.")
            path = (self.config.data_root / asset.relative_path).resolve()
            if (
                not path.is_relative_to((self.config.data_root / "media").resolve())
                or not path.is_file()
            ):
                raise ApiError(404, "MEDIA_NOT_FOUND", "This recording is unavailable.")
            offsets = sample_offsets(asset.duration_seconds, asset.media_type == "image/jpeg")
            media_type = asset.media_type
        inputs, hashes = [], []
        for offset in offsets:
            jpeg = await frame_image(path, offset, self.config, media_type, "balanced")
            hashes.append(hashlib.sha256(jpeg).hexdigest())
            inputs.append({"offset_ms": offset, "jpeg": base64.b64encode(jpeg).decode("ascii")})
        try:
            profiles = self.people.vectors()
        except ApiError:
            profiles = {}
        try:
            if profiles:
                check_recognizer(self.config.sface_model)
        except ApiError:
            profiles = {}
        payload = json.dumps({"frames": inputs, "profiles": profiles}).encode()
        if len(payload) > 24 * 1024**2:
            raise ApiError(422, "FACE_INPUT_LIMIT", "This recording exceeds the detector budget.")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "porchlight.faces.worker",
            str(self.config.face_model.resolve()),
            *((str(self.config.sface_model.resolve()),) if profiles else ()),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(payload), 30)
        except (TimeoutError, asyncio.CancelledError):
            process.kill()
            await process.communicate()
            raise
        if process.returncode != 0 or len(output) > 256 * 1024:
            raise ApiError(
                422, "FACE_DETECTOR_FAILED", "The local detector could not process this recording."
            )
        report = FaceReport.model_validate_json(output)
        if report.policy != POLICY:
            raise ValueError("Detector sampling policy mismatch")
        if report.recognition_model_sha256 != (RECOGNIZER_MANIFEST["sha256"] if profiles else None):
            raise ValueError("Recognizer evidence mismatch")
        if [f.offset_ms for f in report.frames] != offsets or [
            f.sha256 for f in report.frames
        ] != hashes:
            raise ValueError("Detector evidence mismatch")
        return report

    async def execute(self, job: Job) -> None:
        start = time.monotonic()
        if (
            job.payload.get("policy") != POLICY
            or job.payload.get("model_sha256") != MANIFEST["sha256"]
        ):
            with self.db.session() as session:
                current = session.get(Job, job.id)
                if current:
                    current.status, current.lease_until, current.safe_error = (
                        "failed",
                        None,
                        "FACE_POLICY_CHANGED",
                    )
                    session.commit()
            return
        try:
            report = await asyncio.wait_for(self.detect(job.payload["event_id"]), 220)
            if report.model_sha256 != MANIFEST["sha256"]:
                raise ValueError("Detector model mismatch")
            with self.db.session() as session:
                current = session.get(Job, job.id)
                if not current or not session.get(Event, job.payload["event_id"]):
                    return
                control = session.get(IntegrationState, "face_detection")
                if job.payload.get("automatic") and (
                    not control or not control.values.get("enabled")
                ):
                    current.status, current.lease_until = "expired", None
                    session.commit()
                    return
                row = session.get(FaceDetection, job.payload["event_id"])
                created_at = datetime.now(UTC).isoformat()
                elapsed = time.monotonic() - start
                if row:
                    report = preserve_manual_labels(FaceReport.model_validate(row.report), report)
                    row.job_id, row.report = job.id, report.model_dump(mode="json")
                    row.created_at, row.elapsed_seconds = created_at, elapsed
                else:
                    session.add(
                        FaceDetection(
                            event_id=job.payload["event_id"],
                            job_id=job.id,
                            report=report.model_dump(mode="json"),
                            created_at=created_at,
                            elapsed_seconds=elapsed,
                        )
                    )
                current.status, current.lease_until, current.safe_error = "done", None, None
                session.commit()
            try:
                await self.maybe_add_automatic_samples(job.payload["event_id"], report)
            except Exception:
                # An optional profile update must never invalidate an accepted scan.
                logger.warning('{"event":"face_auto_enroll_skipped","code":"LOCAL_FAILURE"}')
        except asyncio.CancelledError:
            # The child is killed and reaped by detect before the application lock is released.
            raise
        except Exception:
            with self.db.session() as session:
                current = session.get(Job, job.id)
                if current:
                    current.status = "queued" if current.attempt < 3 else "failed"
                    current.available_at, current.lease_until = (
                        time.time() + 30 * current.attempt,
                        None,
                    )
                    current.safe_error = (
                        "FACE_DETECTION_RETRY" if current.attempt < 3 else "FACE_DETECTION_FAILED"
                    )
                    session.commit()
            logger.warning('{"event":"face_detection_retry","code":"DETECTOR_UNAVAILABLE"}')

    async def maybe_add_automatic_samples(self, event_id: str, report: FaceReport) -> int:
        """Add at most one exemplar per person/clip from repeated, strong clear matches."""
        if not self.control().get("auto_enroll_enabled"):
            return 0
        manual_profiles = self.people.manual_vectors()
        if not manual_profiles:
            return 0
        groups: dict[str, list[tuple[int, FaceBox]]] = {}
        manually_labeled = {
            str(box.profile_id)
            for frame in report.frames for box in frame.faces
            if box.profile_id and box.match_score is None
        }
        for frame in report.frames:
            for box in frame.faces:
                if (
                    box.profile_id and box.match_score is not None
                    and box.match_score >= 0.75 and box.score >= 0.9
                    and not box.small and not box.low_sharpness
                ):
                    groups.setdefault(str(box.profile_id), []).append((frame.offset_ms, box))
        added = 0
        for person_id, appearances in groups.items():
            if person_id in manually_labeled or len({offset for offset, _ in appearances}) < 2:
                continue
            offset, box = max(
                appearances,
                key=lambda item: (
                    item[1].match_score or 0,
                    min(item[1].width, item[1].height),
                ),
            )
            jpeg = await self.sample_frame(event_id, offset)
            try:
                feature = await asyncio.wait_for(asyncio.to_thread(
                    feature_for_box, jpeg, self.config.face_model,
                    self.config.sface_model, box,
                ), 30)
            except (ValueError, TimeoutError):
                continue
            scores = rank_profiles(feature, manual_profiles)
            if not scores or scores[0][0] != person_id or scores[0][1] < 0.75:
                continue
            if len(scores) > 1 and scores[0][1] - scores[1][1] < 0.15:
                continue
            if self.people.add_automatic_sample(UUID(person_id), feature, event_id):
                added += 1
        return added

    def notify_recording(self) -> None:
        self.wake.set()

    async def run(self) -> None:
        while True:
            self.wake.clear()
            try:
                self.schedule()
                job = self.claim()
                if job:
                    await self.execute(job)
                    continue
            except ApiError:
                pass  # Optional setup is absent; ingestion and Qwen continue independently.
            except Exception:
                logger.warning('{"event":"face_worker_retry","code":"WORKER_UNAVAILABLE"}')
            try:
                await asyncio.wait_for(self.wake.wait(), 5)
            except TimeoutError:
                pass
