"""A deliberately small allowlist export; private records and exception text stay local."""

from __future__ import annotations

import platform
import shutil
import sqlite3
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from uuid import UUID

from sqlalchemy import func, select

from porchlight import __version__
from porchlight.ai.observations import VALIDATION_REASONS
from porchlight.config import Config
from porchlight.operations import contained
from porchlight.retention import settings_and_usage
from porchlight.storage.database import Database, current_revision
from porchlight.storage.models import (
    Analysis,
    CameraCommand,
    Capture,
    Event,
    Job,
    MediaAsset,
    Notification,
    NotificationRule,
    PushDelivery,
    PushDevice,
    RecordingReference,
    RecordingScan,
    SavedView,
)


def support_report(config: Config, db: Database) -> dict[str, object]:
    packages: dict[str, str] = {}
    for name in (
        "fastapi",
        "sqlalchemy",
        "alembic",
        "blinkpy",
        "httpx",
        "pywebpush",
        "cryptography",
    ):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not_installed"
    with db.session() as session:
        settings, used = settings_and_usage(session)
        counts = {
            model.__tablename__: int(session.scalar(select(func.count()).select_from(model)) or 0)
            for model in (
                Event,
                MediaAsset,
                Analysis,
                Capture,
                Notification,
                NotificationRule,
                RecordingReference,
                SavedView,
                PushDevice,
                PushDelivery,
                CameraCommand,
            )
        }
        jobs = {
            kind: {
                status: int(
                    session.scalar(
                        select(func.count())
                        .select_from(Job)
                        .where(Job.type == kind, Job.status == status)
                    )
                    or 0
                )
                for status in ("queued", "running", "done", "failed", "blocked")
            }
            for kind in ("blink_discover", "blink_history", "blink_download", "ai_analyze")
        }
        validation_failures = {
            reason: int(
                session.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(
                        Job.type == "ai_analyze",
                        Job.payload["validation_reason"].as_string() == reason,
                    )
                )
                or 0
            )
            for reason in sorted(VALIDATION_REASONS)
        }
        missing = invalid = checked = 0
        paths = list(session.scalars(select(MediaAsset.relative_path).limit(10000)))
        for row in session.scalars(select(Capture).where(Capture.state == "ready").limit(10000)):
            try:
                suffix = ".mp4" if row.kind == "recording" else ".jpg"
                paths.append(f"media/live-library/{UUID(row.id)}{suffix}")
            except ValueError:
                invalid += 1
        for relative in paths:
            checked += 1
            try:
                missing += not contained(config.data_root, relative).is_file()
            except (ValueError, OSError):
                invalid += 1
        scans = {
            "enabled_count": int(
                session.scalar(
                    select(func.count()).select_from(RecordingScan).where(RecordingScan.enabled)
                )
                or 0
            ),
            "last_checked_epoch": session.scalar(select(func.max(RecordingScan.checked_at))),
        }
    try:
        free: int | None = shutil.disk_usage(config.data_root).free
    except OSError:
        free = None
    return {
        "ai_validation_failures": validation_failures,
        "format": "porchlight-redacted-diagnostics-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "version": __version__,
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "schema": current_revision(db.engine),
        "packages": packages,
        "counts": counts,
        "jobs": jobs,
        "media_check": {
            "checked": checked,
            "missing": missing,
            "invalid_paths": invalid,
            "bounded": checked >= 10000,
        },
        "storage": {
            "archive_bytes": used,
            "free_bytes": free,
            "reserve_bytes": settings.reserve_gib * 1024**3,
            "budget_bytes": settings.archive_budget_gib * 1024**3,
        },
        "settings": {
            "automatic_ai": settings.ai_enabled,
            "automatic_retention": settings.retention_enabled,
            "public_origin_configured": bool(config.public_origin),
        },
        "recording_sync": scans,
        "media_tools": {name: config.tool_path(name) is not None for name in ("ffmpeg", "ffprobe")},
        "excluded": [
            "credentials",
            "subscriptions",
            "keys",
            "account_and_camera_names",
            "model_names",
            "paths",
            "media",
            "descriptions",
            "notes",
            "record_ids",
            "raw_errors",
        ],
    }
