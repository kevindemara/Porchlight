from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import portalocker
from sqlalchemy import Select, and_, delete, func, or_, select, text
from sqlalchemy.orm import Session

from porchlight.api.contracts import ApiError, EventFilters
from porchlight.config import Config
from porchlight.storage.database import Database
from porchlight.storage.models import (
    Analysis,
    Capture,
    Event,
    FileDeletion,
    Job,
    MediaAsset,
    RecordingReference,
    Tombstone,
)


def event_query(filters: EventFilters, timezone: str = "UTC") -> Select[Event, MediaAsset]:
    """Parameter-bound filters; category/colour/direction must match the same entity."""
    if filters.start and filters.end and filters.start >= filters.end:
        raise ApiError(422, "INVALID_TIME_RANGE", "End time must be after start time.")
    result = select(Event, MediaAsset).join(MediaAsset, Event.media_id == MediaAsset.id)
    event_time = func.coalesce(Event.captured_at, Event.discovered_at)
    if filters.camera_ids:
        result = result.where(Event.camera_id.in_(filters.camera_ids))
    if filters.daypart != "all":
        result = result.where(func.porchlight_daypart(event_time, timezone) == filters.daypart)
    for column, value in (
        (Event.camera_id, filters.camera_id),
        (Event.source_type, filters.source),
        (Event.analysis_status, filters.analysis),
    ):
        if value is not None:
            result = result.where(column == value)
    if filters.start:
        result = result.where(event_time >= filters.start.isoformat())
    if filters.end:
        result = result.where(event_time < filters.end.isoformat())
    if filters.favourites:
        result = result.where(Event.favourite.is_(True))
    if filters.query:
        if "\x00" in filters.query:
            raise ApiError(
                422, "INVALID_SEARCH_TEXT", "Search text cannot contain a null character."
            )
        if len(filters.query) >= 3:
            # One quoted literal phrase: user text never becomes FTS operators or SQL.
            phrase = '"' + filters.query.replace('"', '""') + '"'
            result = result.where(
                text(
                    "events.rowid IN (SELECT rowid FROM event_search "
                    "WHERE event_search MATCH :search_phrase)"
                ).bindparams(search_phrase=phrase)
            )
        else:
            # Trigram indices need at least three Unicode characters. Tiny literal searches
            # remain useful, including percent/underscore without wildcard semantics.
            escaped = filters.query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            result = result.where(
                or_(
                    Event.note.ilike(f"%{escaped}%", escape="\\"),
                    Event.summary.ilike(f"%{escaped}%", escape="\\"),
                    Event.corrected_summary.ilike(f"%{escaped}%", escape="\\"),
                    Event.labels_summary.ilike(f"%{escaped}%", escape="\\"),
                )
            )
    terms: list[str] = []
    bindings: dict[str, str] = {}
    if filters.categories:
        terms.append(
            "("
            + " OR ".join(
                f"json_extract(entity.value, '$.category') = :category_{index}"
                for index in range(len(filters.categories))
            )
            + ")"
        )
        bindings.update(
            {f"category_{index}": value for index, value in enumerate(filters.categories)}
        )
    for field in ("category", "color", "direction"):
        value = getattr(filters, field)
        if value:
            terms.append(f"json_extract(entity.value, '$.{field}') = :entity_{field}")
            bindings[f"entity_{field}"] = value
    if filters.action:
        terms.append(
            "EXISTS (SELECT 1 FROM json_each(entity.value, '$.actions') action "
            "WHERE action.value = :entity_action)"
        )
        bindings["entity_action"] = filters.action
    if terms:
        result = result.where(
            text(
                "EXISTS (SELECT 1 FROM json_each(COALESCE(events.corrected_entities, "
                "(SELECT json_extract(observation, '$.entities') FROM analyses "
                "WHERE event_id = events.id ORDER BY revision DESC LIMIT 1))) entity WHERE "
                + " AND ".join(terms)
                + ")"
            ).bindparams(**bindings)
        )
    return result


def after_cursor(statement: Select[Event, MediaAsset], after: Event) -> Select[Event, MediaAsset]:
    event_time = func.coalesce(Event.captured_at, Event.discovered_at)
    instant = after.captured_at or after.discovered_at
    return statement.where(
        or_(event_time < instant, and_(event_time == instant, Event.id < after.id))
    )


class Archive:
    def __init__(self, config: Config, db: Database):
        self.config, self.db = config, db

    @staticmethod
    def remove_event(db: Session, event: Event) -> None:
        jobs = list(db.scalars(select(Job).where(Job.type.in_(["ai_analyze", "face_detect"]))))
        affected = [job for job in jobs if job.payload.get("event_id") == event.id]
        if any(job.status == "running" for job in affected):
            raise ApiError(409, "ANALYSIS_BUSY", "Wait for this recording's analysis to finish.")
        db.execute(delete(Analysis).where(Analysis.event_id == event.id))
        for job in affected:
            db.delete(job)
        for reference in db.scalars(
            select(RecordingReference).where(RecordingReference.event_id == event.id)
        ):
            reference.event_id, reference.state = None, "deleted"
        if not db.get(Tombstone, event.source_key):
            db.add(Tombstone(source_key=event.source_key, deleted_at=datetime.now(UTC).isoformat()))
        asset_id = event.media_id
        db.delete(event)
        db.flush()
        remaining = db.scalar(
            select(func.count()).select_from(Event).where(Event.media_id == asset_id)
        )
        if not remaining:
            asset = db.get(MediaAsset, asset_id)
            assert asset
            for path in (asset.relative_path, f"thumbnails/{asset.id}-v1.jpg"):
                if not db.get(FileDeletion, path):
                    db.add(FileDeletion(relative_path=path))
            db.delete(asset)

    def delete_event(self, event_id: str) -> None:
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            event = db.get(Event, event_id)
            if not event:
                raise ApiError(404, "EVENT_NOT_FOUND", "This recording is unavailable.")
            self.remove_event(db, event)
            db.commit()
        self.recover_deletions()

    @staticmethod
    def remove_capture(db: Session, capture: Capture) -> None:
        if capture.state in {"recording", "saving"}:
            raise ApiError(409, "CAPTURE_BUSY", "Wait for this capture to finish saving.")
        for suffix in (".mp4", ".jpg", ".part", ".saving.mp4", ".saving.jpg"):
            relative = f"media/live-library/{capture.id}{suffix}"
            if not db.get(FileDeletion, relative):
                db.add(FileDeletion(relative_path=relative))
        thumbnail = f"thumbnails/{capture.id}-v1.jpg"
        if not db.get(FileDeletion, thumbnail):
            db.add(FileDeletion(relative_path=thumbnail))
        db.delete(capture)

    def delete_capture(self, capture_id: str) -> None:
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            capture = db.get(Capture, capture_id)
            if not capture:
                raise ApiError(404, "CAPTURE_NOT_FOUND", "This capture is unavailable.")
            self.remove_capture(db, capture)
            db.commit()
        self.recover_deletions()

    def recover_deletions(self) -> None:
        with (
            portalocker.Lock(self.config.data_root / "media.lock", timeout=10),
            self.db.session() as db,
        ):
            for row in db.scalars(select(FileDeletion)):
                if db.scalar(
                    select(MediaAsset.id).where(MediaAsset.relative_path == row.relative_path)
                ):
                    db.delete(row)
                    continue
                relative = Path(row.relative_path)
                path = (self.config.data_root / relative).resolve()
                if not any(
                    path.is_relative_to((self.config.data_root / folder).resolve())
                    for folder in ("media", "thumbnails")
                ):
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    continue  # Windows open-file handles retry after playback releases them.
                db.delete(row)
            db.commit()
