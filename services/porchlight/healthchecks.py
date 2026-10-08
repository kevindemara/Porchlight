"""Independent owner-visible checks; timestamps describe the operation actually observed."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import func, select

from porchlight.api.contracts import (
    AnalysisStatus,
    BlinkStatus,
    Component,
    DiagnosticCheck,
    PushStatus,
)
from porchlight.storage.database import Database
from porchlight.storage.models import Analysis, Event, Job, RecordingReference, RecordingScan


def instant(epoch: float | None) -> str | None:
    return datetime.fromtimestamp(epoch, UTC).isoformat() if epoch else None


def checks(
    db: Database,
    blink: BlinkStatus,
    inventory_at: float,
    ai: AnalysisStatus,
    push: PushStatus,
    storage: Component,
    workers: dict[str, tuple[float, bool]],
) -> list[DiagnosticCheck]:
    with db.session() as session:
        latest_scan = session.scalar(select(func.max(RecordingScan.checked_at)))
        saved = session.scalar(
            select(func.max(Event.discovered_at)).where(
                Event.source_type.in_(["blink_cloud", "blink_local"])
            )
        )
        analyzed = session.scalar(select(func.max(Analysis.created_at)))
        pending = int(
            session.scalar(
                select(func.count())
                .select_from(RecordingReference)
                .where(RecordingReference.state == "pending")
            )
            or 0
        )
        failed = int(
            session.scalar(
                select(func.count())
                .select_from(RecordingReference)
                .where(RecordingReference.state.in_(["failed", "blocked"]))
            )
            or 0
        )
        jobs = dict(
            session.execute(
                select(Job.status, func.count())
                .where(Job.type.in_(["blink_discover", "blink_history"]))
                .group_by(Job.status)
            ).all()
        )
        enabled = int(
            session.scalar(
                select(func.count()).select_from(RecordingScan).where(RecordingScan.enabled)
            )
            or 0
        )
    result = [
        DiagnosticCheck(
            key="blink_auth",
            label="Blink sign-in",
            state="ready"
            if blink.state == "connected"
            else "not_configured"
            if blink.state == "not_configured"
            else "unavailable",
            message="Session restored or authenticated; recording access is checked separately."
            if blink.state == "connected"
            else "Blink sign-in needs attention.",
            action=None if blink.state == "connected" else "Open Blink connection above.",
        ),
        DiagnosticCheck(
            key="inventory",
            label="Camera inventory",
            state="ready" if inventory_at and time.time() - inventory_at < 600 else "unverified",
            message="Inventory was refreshed recently."
            if inventory_at and time.time() - inventory_at < 600
            else "Inventory has not been refreshed recently; camera information may be older.",
            last_success_at=instant(inventory_at),
            action="Refresh cameras to check their current state.",
        ),
        DiagnosticCheck(
            key="listing",
            label="Clip listing",
            state="unavailable"
            if jobs.get("failed", 0) or jobs.get("blocked", 0)
            else "disabled"
            if not enabled
            else "ready"
            if latest_scan
            else "unverified",
            message="A complete recording scan has been saved."
            if latest_scan
            else "No complete recording scan has been observed.",
            last_success_at=instant(latest_scan),
            queued=jobs.get("queued", 0),
            running=jobs.get("running", 0),
            needs_attention=jobs.get("failed", 0) + jobs.get("blocked", 0),
            action="Review cloud/local sync and historical retrieval above.",
        ),
        DiagnosticCheck(
            key="downloads",
            label="Clip downloads",
            state="unavailable" if failed else "ready" if saved else "unverified",
            message="Last success is a saved Blink clip; downloads may remain pending."
            if saved
            else "No Blink recording has been saved locally yet.",
            last_success_at=saved,
            queued=pending,
            needs_attention=failed,
            safe_error="RECORDING_ATTENTION" if failed else None,
            action="Review recording sync; preserved clips remain playable.",
        ),
        DiagnosticCheck(
            key="ai",
            label="Local AI",
            state="ready" if ai.ready else "unverified",
            message="Automatic analysis is enabled."
            if ai.enabled
            else "Automatic analysis is paused; manual review uses the selected tested model.",
            last_success_at=analyzed,
            queued=ai.queued,
            running=ai.running,
            needs_attention=ai.failed,
            safe_error="AI_JOBS_ATTENTION" if ai.failed else None,
            action="Test the selected model or retry a failed recording.",
        ),
        DiagnosticCheck(
            key="disk",
            label="Archive storage",
            state=storage.state,
            message=storage.message,
            action="Review the storage reserve and archive budget."
            if storage.state != "ready"
            else None,
        ),
        DiagnosticCheck(
            key="push",
            label="Phone delivery",
            state="unverified" if push.configured else "not_configured",
            message="Pair a phone and verify a test. Provider acceptance does not prove delivery.",
            action="Open Notifications to review pairing and delivery states.",
        ),
    ]
    for key, label, threshold in [
        ("recordings", "Cloud archive worker", 300),
        ("local_recordings", "Local-source worker", 300),
        ("analysis", "AI worker", 300),
        ("notifications", "Local inbox worker", 30),
        ("push", "Phone delivery worker", 300),
    ]:
        last_tick, active = workers.get(key, (0, False))
        healthy = active and bool(last_tick) and time.time() - last_tick < threshold
        result.append(
            DiagnosticCheck(
                key=f"worker_{key}",
                label=label,
                state="ready" if healthy else "unavailable",
                heartbeat_at=instant(last_tick),
                message="Worker loop is responsive; source and phone checks are separate."
                if healthy
                else "Worker loop has stopped or has not checked in within its operation deadline.",
                safe_error=None if healthy else "WORKER_STALE",
                action=None
                if healthy
                else "Review diagnostics and restart Porchlight if the check remains stale.",
            )
        )
    return result
