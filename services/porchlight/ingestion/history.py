from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from porchlight.api.contracts import ApiError, HistoryControl, RecordingHistory
from porchlight.storage.database import Database
from porchlight.storage.models import Job, RecordingReference, RecordingScan


def history_id(source: str) -> str:
    return f"{source}:history"


def history_view(db: Session, source: str) -> RecordingHistory:
    scan = db.get(RecordingScan, history_id(source))
    if not scan:
        return RecordingHistory()
    counts = dict(
        db.execute(
            select(RecordingReference.state, func.count())
            .where(RecordingReference.source_id == source, RecordingReference.historical.is_(True))
            .group_by(RecordingReference.state)
        ).all()
    )
    job = db.scalar(select(Job).where(Job.dedup_key == f"history:{source}"))
    pending = counts.get("pending", 0)
    failed = counts.get("failed", 0) + counts.get("expired", 0)
    state: str = "complete"
    if not scan.enabled:
        state = "paused"
    elif failed or (job and job.safe_error):
        state = "needs_attention"
    elif scan.checked_at is None:
        state = "scanning" if job and job.status == "running" else "queued"
    elif pending:
        state = "downloading"
    return RecordingHistory.model_validate(
        {
            "state": state,
            "days": scan.history_days,
            "discovered": sum(counts.values()),
            "archived": counts.get("archived", 0),
            "pending": pending,
            "failed": failed,
            "checked_at": datetime.fromtimestamp(scan.checked_at, UTC).isoformat()
            if scan.checked_at
            else None,
        }
    )


def history_control(database: Database, source: str, body: HistoryControl) -> None:
    """Invalidate in-flight page results atomically; retain downloads and provider backoff."""
    now = time.time()
    with database.session() as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        regular = db.get(RecordingScan, source)
        if regular is None:
            db.add(RecordingScan(id=source, enabled=False, since=now - 7 * 86400, page=1))
        scan = db.get(RecordingScan, history_id(source))
        if scan is None:
            if body.action != "start":
                raise ApiError(409, "HISTORY_NOT_STARTED", "Choose a history range first.")
            scan = RecordingScan(
                id=history_id(source), enabled=False, since=0, page=1, generation=0
            )
            db.add(scan)
        scan.generation += 1
        if body.action == "start":
            scan.history_days = body.days
            scan.since = max(0, now - body.days * 86400) if body.days else 0
            scan.page, scan.started_at, scan.checked_at = 1, None, None
        scan.enabled = body.action != "pause"
        job = db.scalar(select(Job).where(Job.dedup_key == f"history:{source}"))
        if job is None:
            job = Job(
                id=str(uuid4()),
                type="blink_history",
                dedup_key=f"history:{source}",
                payload={},
                status="queued",
                attempt=0,
                available_at=now,
            )
            db.add(job)
        job.payload = {
            "source_id": source,
            "source_type": "blink_cloud",
            "generation": scan.generation,
        }
        job.status = "done" if scan.checked_at is not None else "queued"
        job.attempt, job.lease_until = 0, None
        # Explicit retry/reset never shortens a provider's Retry-After interval.
        job.available_at = max(now, job.available_at)
        if body.action != "pause":
            job.safe_error = None
            for retry in db.scalars(
                select(Job).where(
                    Job.type == "blink_download",
                    Job.status.in_(["failed", "blocked"]),
                    Job.payload["source_id"].as_string() == source,
                    Job.payload["historical"].as_boolean().is_(True),
                )
            ):
                reference = db.get(RecordingReference, retry.payload["reference_id"])
                if reference and reference.state not in {"expired", "deleted", "archived"}:
                    retry.status, retry.attempt, retry.safe_error = "queued", 0, None
                    retry.available_at = max(now, retry.available_at)
                    reference.state, reference.safe_error = "pending", None
        db.commit()
