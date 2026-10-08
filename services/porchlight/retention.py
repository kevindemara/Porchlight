"""Optional local cleanup, gated by a short-lived, unchanged owner preview."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from porchlight.api.contracts import ApiError, AppSettings, RetentionPreview, RetentionResult
from porchlight.catalog import Archive
from porchlight.config import Config
from porchlight.storage.database import Database
from porchlight.storage.models import Capture, Event, Job, MediaAsset, SettingsRow


def settings_and_usage(db: Session) -> tuple[AppSettings, int]:
    row = db.get(SettingsRow, 1)
    settings = AppSettings(revision=row.revision, **row.values) if row else AppSettings(revision=1)
    used = int(db.scalar(select(func.sum(MediaAsset.bytes))) or 0)
    used += int(db.scalar(select(func.sum(Capture.bytes))) or 0)
    return settings, used


def check_space(config: Config, db: Database, maximum_bytes: int) -> None:
    with db.session() as session:
        settings, used = settings_and_usage(session)
    if shutil.disk_usage(config.data_root).free < settings.reserve_gib * 1024**3 + maximum_bytes:
        raise ApiError(503, "DISK_SPACE_LOW", "Saving is paused to preserve free disk space.", True)
    if used + maximum_bytes > settings.archive_budget_gib * 1024**3:
        raise ApiError(
            503,
            "ARCHIVE_BUDGET_REACHED",
            "Review local storage or increase its budget before saving more recordings.",
            True,
        )


@dataclass
class Plan:
    events: list[Event]
    captures: list[Capture]
    reclaimable: int
    protected: int
    busy: int
    revision: int

    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "events": sorted(event.id for event in self.events),
                    "captures": sorted(capture.id for capture in self.captures),
                    "bytes": self.reclaimable,
                    "revision": self.revision,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()


def plan(db: Session, cutoff: str) -> Plan:
    settings, _ = settings_and_usage(db)
    running = {
        job.payload.get("event_id")
        for job in db.scalars(
            select(Job).where(Job.type.in_(["ai_analyze", "face_detect"]), Job.status == "running")
        )
    }
    events = list(
        db.scalars(
            select(Event)
            .where(func.coalesce(Event.captured_at, Event.discovered_at) < cutoff)
            .order_by(func.coalesce(Event.captured_at, Event.discovered_at), Event.id)
        )
    )
    captures = list(
        db.scalars(
            select(Capture).where(Capture.saved_at < cutoff).order_by(Capture.saved_at, Capture.id)
        )
    )
    protected = sum(event.favourite for event in events) + sum(c.favourite for c in captures)
    busy = sum(event.id in running or event.analysis_status == "analyzing" for event in events)
    busy += sum(capture.state in {"recording", "saving"} for capture in captures)
    eligible = [
        e
        for e in events
        if not e.favourite and e.id not in running and e.analysis_status != "analyzing"
    ]
    saved = [c for c in captures if not c.favourite and c.state in {"ready", "failed"}]
    deleted = {event.id for event in eligible}
    reclaimable = sum(c.bytes for c in saved)
    for asset_id in {event.media_id for event in eligible}:
        references = set(db.scalars(select(Event.id).where(Event.media_id == asset_id)))
        if references <= deleted:
            asset = db.get(MediaAsset, asset_id)
            if asset:
                reclaimable += asset.bytes
    return Plan(eligible, saved, reclaimable, protected, busy, settings.revision)


class Retention:
    def __init__(self, config: Config, db: Database, archive: Archive):
        self.config, self.db, self.archive = config, db, archive
        self.previews: dict[str, tuple[float, int, str, str]] = {}
        self.last_run = 0.0

    def preview(self, days: int) -> RetentionPreview:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self.db.session() as db:
            current = plan(db, cutoff)
        self.previews = {
            key: value for key, value in self.previews.items() if value[0] > time.monotonic()
        }
        if len(self.previews) >= 10:
            self.previews.pop(next(iter(self.previews)))
        token = secrets.token_urlsafe(32)
        self.previews[token] = (time.monotonic() + 300, days, cutoff, current.fingerprint())
        return RetentionPreview(
            token=token,
            days=days,
            cutoff=cutoff,
            event_count=len(current.events),
            capture_count=len(current.captures),
            reclaimable_bytes=current.reclaimable,
            protected_count=current.protected,
            busy_count=current.busy,
            settings_revision=current.revision,
        )

    def apply(self, token: str, enable_automatic: bool) -> RetentionResult:
        reviewed = self.previews.pop(token, None)
        if not reviewed or reviewed[0] <= time.monotonic():
            raise ApiError(409, "PREVIEW_EXPIRED", "Preview cleanup again before confirming.")
        _, days, cutoff, fingerprint = reviewed
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            current = plan(db, cutoff)
            if current.fingerprint() != fingerprint:
                raise ApiError(
                    409, "PREVIEW_CHANGED", "Your archive changed. Review a new preview."
                )
            for event in current.events:
                self.archive.remove_event(db, event)
            for capture in current.captures:
                self.archive.remove_capture(db, capture)
            row = db.get(SettingsRow, 1)
            assert row
            row.values = {
                **row.values,
                "retention_days": days,
                "retention_enabled": enable_automatic,
            }
            row.revision += 1
            db.commit()
        self.archive.recover_deletions()
        return RetentionResult(
            events_deleted=len(current.events),
            captures_deleted=len(current.captures),
            automatic_enabled=enable_automatic,
        )

    def maintain(self) -> None:
        if time.monotonic() - self.last_run < 60:
            return
        self.last_run = time.monotonic()
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            settings, _ = settings_and_usage(db)
            if not settings.retention_enabled:
                return
            cutoff = (datetime.now(UTC) - timedelta(days=settings.retention_days)).isoformat()
            current = plan(db, cutoff)
            for event in current.events[:100]:
                self.archive.remove_event(db, event)
            for capture in current.captures[:100]:
                self.archive.remove_capture(db, capture)
            db.commit()
        self.archive.recover_deletions()
