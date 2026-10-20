from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import case, func, or_, select

from porchlight.api.contracts import ApiError, AppSettings, HistoryControl, RecordingSync
from porchlight.config import Config
from porchlight.ingestion.history import history_control, history_id, history_view
from porchlight.ingestion.imports import MAX_BYTES, Importer, inspect_mp4
from porchlight.providers.base import RecordingPage, RecordingProvider
from porchlight.retention import check_space
from porchlight.storage.database import Database
from porchlight.storage.models import (
    Event,
    Job,
    MediaAsset,
    RecordingReference,
    RecordingScan,
    SettingsRow,
)

RECONCILE_SECONDS = 24 * 60 * 60
RECOVERY_COOLDOWN = 15 * 60
# Only observed temporary failures get recurring recovery. Configuration, expired
# media, authentication and changed contracts must not become endless requests.
TRANSIENT_ERRORS = frozenset(
    {
        "RECORDING_LIST_UNAVAILABLE",
        "RECORDING_WORK_FAILED",
        "BLINK_RATE_LIMITED",
        "CLIP_TRANSFER_FAILED",
        "LOCAL_MODULE_WAIT",
        "LOCAL_MANIFEST_UNAVAILABLE",
        "LOCAL_TRANSFER_UNAVAILABLE",
    }
)


def instant(timestamp: float | None) -> str | None:
    try:
        return datetime.fromtimestamp(timestamp, UTC).isoformat() if timestamp is not None else None
    except (ValueError, OverflowError, OSError):
        return None


class Recordings:
    """One bounded worker over persistent page checkpoints and leased download jobs."""

    def __init__(
        self,
        config: Config,
        db: Database,
        provider: RecordingProvider,
        importer: Importer,
        source_type: Literal["blink_cloud", "blink_local"] = "blink_cloud",
        *,
        on_archived: Callable[[], None] | None = None,
    ):
        self.config, self.db, self.provider, self.importer = config, db, provider, importer
        self.source_type = source_type
        self.poll_interval = config.cloud_poll_seconds if source_type == "blink_cloud" else 120
        self.on_archived = on_archived
        self.wake = asyncio.Event()
        # The caller owns the exclusive process/profile lock; no former worker remains alive.
        with db.session() as session:
            for job in session.scalars(
                select(Job).where(
                    Job.type.in_(["blink_discover", "blink_download", "blink_history"]),
                    Job.status == "running",
                )
            ):
                job.status, job.lease_until = "queued", None
                # It was already due before interruption. A corrected wall clock must
                # not turn its old availability into a new wait. Queued backoff stays intact.
                job.available_at = min(job.available_at, time.time())
            # Apply a shorter configured routine interval after restart without
            # accelerating retries, historical work or another source's jobs.
            for job in session.scalars(
                select(Job).where(
                    Job.type == "blink_discover",
                    Job.status == "queued",
                    Job.attempt == 0,
                    Job.safe_error.is_(None),
                )
            ):
                if job.payload.get("source_type", "blink_cloud") != source_type:
                    continue
                scan = session.get(RecordingScan, job.payload.get("source_id"))
                if scan and scan.enabled and scan.checked_at is not None:
                    job.available_at = min(
                        job.available_at, max(time.time(), scan.checked_at + self.poll_interval)
                    )
            session.commit()

    def source(self) -> str | None:
        try:
            return self.provider.recording_source_id
        except ApiError:
            return None

    def view(self) -> RecordingSync:
        source = self.source()
        if source is None:
            return RecordingSync(
                source=self.source_type,
                poll_interval_seconds=self.poll_interval,
                message="Connect Blink before syncing recordings.",
            )
        with self.db.session() as db:
            scan = db.get(RecordingScan, source)
            if scan is None:
                return RecordingSync(
                    source=self.source_type,
                    poll_interval_seconds=self.poll_interval,
                    message="Recording discovery has not started.",
                )
            settings = db.get(SettingsRow, 1)
            entitlement = (
                AppSettings(revision=settings.revision, **settings.values).blink_entitlement
                if settings
                else AppSettings(revision=1).blink_entitlement
            )
            states = dict(
                db.execute(
                    select(RecordingReference.state, func.count())
                    .where(RecordingReference.source_id == source)
                    .group_by(RecordingReference.state)
                ).all()
            )
            active = db.scalar(select(Job).where(Job.dedup_key == f"discover:{source}"))
            failures = states.get("failed", 0) + states.get("expired", 0)
            state: Any = "ready"
            message = "Available recordings checked. Subscription-free access remains unverified."
            if active and active.status == "running":
                state, message = "syncing", "Checking available recordings."
            elif active and active.status == "queued":
                state, message = "queued", "Recording discovery is scheduled."
            if states.get("failed", 0) or (active and active.status in {"failed", "blocked"}):
                state, message = (
                    "needs_attention",
                    "Some recording work could not complete. "
                    "Sign in if requested or review the reported reason.",
                )
            elif active and active.status == "queued" and active.safe_error in TRANSIENT_ERRORS:
                state, message = (
                    "queued",
                    "Blink is temporarily unavailable. Sync will retry automatically with backoff; "
                    "repeated failures use a longer cooldown. No retry click is needed.",
                )
            elif states.get("expired", 0):
                message += " Older expired clips cannot be recovered; new clip checks continue."
            return RecordingSync(
                source=self.source_type,
                poll_interval_seconds=self.poll_interval,
                enabled=scan.enabled,
                history=history_view(db, source),
                discovered=sum(states.values()),
                archived=states.get("archived", 0),
                pending=states.get("pending", 0),
                failed=failures,
                last_checked_at=instant(scan.checked_at),
                next_sync_at=instant(active.available_at)
                if active and active.status == "queued"
                else None,
                incomplete=scan.started_at is not None,
                state=state,
                message=message,
                entitlement=entitlement,
                entitlement_provenance="unknown" if entitlement == "unknown" else "owner_confirmed",
                last_error_code=active.safe_error
                if active and active.safe_error
                else db.scalar(
                    select(RecordingReference.safe_error)
                    .where(
                        RecordingReference.source_id == source,
                        RecordingReference.safe_error.is_not(None),
                    )
                    .limit(1)
                ),
            )

    def control(self, enabled: bool) -> RecordingSync:
        source = self.provider.recording_source_id
        now = time.time()
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            scan = db.get(RecordingScan, source)
            if scan is None:
                scan = RecordingScan(id=source, enabled=enabled, since=now - 7 * 86400, page=1)
                db.add(scan)
                db.flush()
            scan.enabled = enabled
            job = db.scalar(select(Job).where(Job.dedup_key == f"discover:{source}"))
            if job is None and enabled:
                db.add(
                    Job(
                        id=str(uuid4()),
                        type="blink_discover",
                        dedup_key=f"discover:{source}",
                        payload={"source_id": source, "source_type": self.source_type},
                        status="queued",
                        attempt=0,
                        available_at=now,
                        lease_until=None,
                        safe_error=None,
                    )
                )
            elif job and enabled and job.status in {"failed", "blocked", "done"}:
                job.status, job.attempt, job.available_at, job.safe_error = (
                    "queued",
                    0,
                    max(now, job.available_at, (scan.checked_at or 0) + self.poll_interval),
                    None,
                )
            if enabled:
                for retry in db.scalars(
                    select(Job).where(
                        Job.type == "blink_download", Job.status.in_(["failed", "blocked"])
                    )
                ):
                    if retry.payload.get("source_id") == source and not retry.payload.get(
                        "historical"
                    ):
                        reference = db.get(RecordingReference, retry.payload["reference_id"])
                        if reference and reference.state != "expired":
                            retry.status, retry.attempt, retry.available_at, retry.safe_error = (
                                "queued",
                                0,
                                max(now, retry.available_at),
                                None,
                            )
                            reference.state, reference.safe_error = "pending", None
            db.commit()
        self.wake.set()
        return self.view()

    def history(self, body: HistoryControl) -> RecordingSync:
        if self.source_type != "blink_cloud":
            raise ApiError(
                409, "HISTORY_UNSUPPORTED", "Historical ranges apply to Blink cloud clips."
            )
        history_control(self.db, self.provider.recording_source_id, body)
        self.wake.set()
        return self.view()

    def claim(self) -> Job | None:
        source = self.source()
        if source is None:
            return None
        now = time.time()
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            scan = db.get(RecordingScan, source)
            history = db.get(RecordingScan, history_id(source))
            regular_enabled = bool(scan and scan.enabled)
            history_enabled = bool(
                history and history.enabled and self.source_type == "blink_cloud"
            )
            if not regular_enabled and not history_enabled:
                return None
            historical = func.coalesce(Job.payload["historical"].as_boolean(), False)
            eligible = or_(
                (Job.type == "blink_history") & history_enabled,
                (Job.type == "blink_download") & historical & history_enabled,
                (Job.type != "blink_history") & ~historical & regular_enabled,
            )
            # Upgrade previously failed temporary work without a manual retry.
            # Persist the cooldown once, respecting any longer provider delay.
            for retry in db.scalars(
                select(Job).where(
                    Job.type.in_(["blink_discover", "blink_download", "blink_history"]),
                    Job.status == "failed",
                    Job.safe_error.in_(TRANSIENT_ERRORS),
                    Job.payload["source_id"].as_string() == source,
                    func.coalesce(Job.payload["source_type"].as_string(), "blink_cloud")
                    == self.source_type,
                    eligible,
                )
            ):
                reference = (
                    db.get(RecordingReference, retry.payload.get("reference_id"))
                    if retry.type == "blink_download"
                    else None
                )
                if retry.type == "blink_download" and (
                    reference is None or reference.state in {"archived", "expired", "deleted"}
                ):
                    continue
                retry.status, retry.attempt, retry.lease_until = "queued", 0, None
                retry.available_at = max(retry.available_at, now + RECOVERY_COOLDOWN)
                if reference:
                    reference.state = "pending"
            db.flush()
            job = db.scalar(
                select(Job)
                .where(
                    Job.type.in_(["blink_discover", "blink_download", "blink_history"]),
                    eligible,
                    func.coalesce(Job.payload["source_type"].as_string(), "blink_cloud")
                    == self.source_type,
                    or_(
                        (Job.status == "queued") & (Job.available_at <= now),
                        (Job.status == "running") & (Job.lease_until < now),
                    ),
                )
                .order_by(
                    case((Job.type == "blink_history", 2), (historical, 3), else_=0),
                    Job.available_at,
                    Job.id,
                )
                .limit(1)
            )
            # A saved job for another account cannot be executed with the current actor.
            if job and job.payload.get("source_id") != source:
                job.status, job.safe_error = "blocked", "ACCOUNT_CHANGED"
                db.commit()
                return None
            if job:
                if job.attempt >= 4:
                    # The process can stop during its fourth attempt, before
                    # execute() persists the cooldown. Retain a known temporary
                    # error and recover without an extra immediate request.
                    if job.safe_error in TRANSIENT_ERRORS:
                        job.status, job.attempt, job.lease_until = "queued", 0, None
                        job.available_at = max(job.available_at, now + RECOVERY_COOLDOWN)
                    else:
                        job.status, job.safe_error = "failed", "ATTEMPTS_EXHAUSTED"
                    db.commit()
                    return None
                job.status, job.attempt, job.lease_until = "running", job.attempt + 1, now + 300
            db.commit()
            return job

    def persist_page(
        self,
        source: str,
        result: RecordingPage,
        *,
        generation: int | None = None,
        page: int | None = None,
        historical: bool = False,
    ) -> bool:
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            scan = db.get(RecordingScan, history_id(source) if historical else source)
            assert scan is not None
            if generation is not None and (
                not scan.enabled or scan.generation != generation or scan.page != page
            ):
                return False
            for clip in result.clips:
                reference = db.scalar(
                    select(RecordingReference).where(
                        RecordingReference.source_key == clip.source_key
                    )
                )
                if reference:
                    if reference.state not in {"archived", "deleted"}:
                        reference.media_path = clip.media_path
                        if clip.deleted:
                            reference.state, reference.safe_error = (
                                "expired",
                                "SOURCE_MEDIA_EXPIRED",
                            )
                            job = db.scalar(
                                select(Job).where(Job.dedup_key == f"download:{reference.id}")
                            )
                            if job:
                                job.status = "done"
                    continue
                reference = RecordingReference(
                    id=str(uuid4()),
                    source_key=clip.source_key,
                    source_id=source,
                    source_type=self.source_type,
                    camera_id=clip.camera_id,
                    captured_at=clip.captured_at,
                    raw_timestamp=clip.raw_timestamp,
                    discovered_at=datetime.now(UTC).isoformat(),
                    media_path=clip.media_path,
                    state="expired" if clip.deleted else "pending",
                    event_id=None,
                    safe_error="SOURCE_MEDIA_EXPIRED" if clip.deleted else None,
                    historical=historical,
                )
                db.add(reference)
                db.flush()
                if not clip.deleted:
                    db.add(
                        Job(
                            id=str(uuid4()),
                            type="blink_download",
                            dedup_key=f"download:{reference.id}",
                            payload={
                                "source_id": source,
                                "reference_id": reference.id,
                                "source_type": self.source_type,
                                "historical": historical,
                            },
                            status="queued",
                            attempt=0,
                            available_at=time.time(),
                            lease_until=None,
                            safe_error=None,
                        )
                    )
            if result.exhausted:
                # Advance after durable complete coverage; overlap covers delayed clips.
                if not historical:
                    scan.since = max(scan.since, (scan.started_at or time.time()) - 300)
                scan.page, scan.started_at, scan.checked_at = 1, None, time.time()
            else:
                scan.page += 1
            db.commit()
            return True

    async def discover(self, source: str) -> None:
        await self.discover_pages(source)

    async def discover_pages(self, source: str, history_generation: int | None = None) -> None:
        historical = history_generation is not None
        scan_id = history_id(source) if historical else source
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            scan = db.get(RecordingScan, scan_id)
            assert scan is not None
            if not scan.enabled or (historical and scan.generation != history_generation):
                return
            generation = scan.generation
            if scan.started_at is None:
                scan.started_at = time.time()
                if not historical and self.source_type == "blink_cloud":
                    # Blink can expose clips after their original timestamp has fallen
                    # behind the incremental cursor. Reconcile a bounded recent window;
                    # source keys deduplicate repeats. Preserve older initial/backfill
                    # coverage and an interrupted scan's exact cutoff/page.
                    scan.since = min(scan.since, scan.started_at - RECONCILE_SECONDS)
                db.commit()
        # Work is bounded per lease; a large history resumes at its saved page next cycle.
        for _ in range(20):
            with self.db.session() as db:
                scan = db.get(RecordingScan, scan_id)
                assert scan is not None
                if not scan.enabled or scan.generation != generation:
                    return
                since, page = scan.since, scan.page
            result = await self.provider.recording_page(since, page)
            accepted = self.persist_page(
                source, result, generation=generation, page=page, historical=historical
            )
            if not accepted or result.exhausted:
                return
            await asyncio.sleep(0.25)

    async def download(self, reference_id: str) -> None:
        with self.db.session() as db:
            reference = db.get(RecordingReference, reference_id)
            if reference is None or reference.state in {"archived", "expired", "deleted"}:
                return
            recovered = db.scalar(select(Event).where(Event.source_key == reference.source_key))
            recovered_asset = db.get(MediaAsset, recovered.media_id) if recovered else None
            if (
                recovered
                and recovered_asset
                and (self.config.data_root / recovered_asset.relative_path).is_file()
            ):
                reference.state, reference.event_id, reference.safe_error = (
                    "archived",
                    recovered.id,
                    None,
                )
                db.commit()
                if self.on_archived:
                    self.on_archived()
                return
            manifest: dict[str, Any] = {
                "source_key": reference.source_key,
                "source_type": reference.source_type,
                "camera_id": reference.camera_id,
                "captured_at": reference.captured_at,
                "discovered_at": reference.discovered_at,
                "timestamp_quality": "upstream" if reference.captured_at else "unknown",
                "historical": reference.historical,
            }
            path = reference.media_path
        if not self.config.tool_path("ffmpeg") or not self.config.tool_path("ffprobe"):
            raise ApiError(
                503, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg before recording downloads.", True
            )
        check_space(self.config, self.db, MAX_BYTES)
        temporary = self.importer.scratch / f"{uuid4()}.part"
        try:
            await self.provider.download_recording(path, temporary)
            metadata = await inspect_mp4(temporary, self.config)
            with temporary.open("rb") as handle:
                sha = hashlib.file_digest(handle, "sha256").hexdigest()
            manifest.update(metadata, sha256=sha, bytes=temporary.stat().st_size)
            journal = self.importer.scratch / f"{uuid4()}.import.json"
            with journal.open("x", encoding="utf-8") as handle:
                json.dump(manifest, handle)
                handle.flush()
                os.fsync(handle.fileno())
            event_id = self.importer.commit_import(manifest, temporary)
            with self.db.session() as db:
                reference = db.get(RecordingReference, reference_id)
                assert reference is not None
                reference.event_id, reference.state, reference.safe_error = (
                    event_id,
                    "archived",
                    None,
                )
                db.commit()
            journal.unlink()
            if self.on_archived:
                self.on_archived()
        finally:
            temporary.unlink(missing_ok=True)

    async def execute(self, claimed: Job) -> None:
        error: ApiError | None = None
        try:
            async with asyncio.timeout(240):
                if claimed.type == "blink_discover":
                    await self.discover(claimed.payload["source_id"])
                elif claimed.type == "blink_history":
                    await self.discover_pages(
                        claimed.payload["source_id"], claimed.payload["generation"]
                    )
                else:
                    await self.download(claimed.payload["reference_id"])
        except ApiError as exc:
            error = exc
        except Exception:
            error = ApiError(
                503, "RECORDING_WORK_FAILED", "Recording work could not complete.", True
            )
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            job = db.get(Job, claimed.id)
            assert job is not None
            if claimed.type == "blink_history" and job.payload.get(
                "generation"
            ) != claimed.payload.get("generation"):
                return
            job.lease_until = None
            if error:
                job.safe_error = error.code
                cooldown = error.retryable and error.code in TRANSIENT_ERRORS and job.attempt >= 4
                job.status = (
                    "blocked"
                    if error.code == "BLINK_AUTH_REQUIRED"
                    else "queued"
                    if error.retryable and (job.attempt < 4 or cooldown)
                    else "failed"
                )
                job.available_at = (
                    time.time()
                    + max(
                        RECOVERY_COOLDOWN if cooldown else 120,
                        30 * 2**job.attempt,
                        error.retry_after or 0,
                    )
                    + random.uniform(0, 10)
                )
                if cooldown:
                    job.attempt = 0
                if job.type == "blink_download":
                    reference = db.get(RecordingReference, job.payload["reference_id"])
                    if reference:
                        reference.safe_error = error.code
                        reference.state = (
                            "expired"
                            if error.code == "SOURCE_MEDIA_EXPIRED"
                            else "failed"
                            if job.status in {"failed", "blocked"}
                            else "pending"
                        )
            elif job.type in {"blink_discover", "blink_history"}:
                interval = self.poll_interval if job.type == "blink_discover" else 120
                job.status, job.attempt, job.available_at, job.safe_error = (
                    "queued",
                    0,
                    time.time() + interval + random.uniform(0, min(10, interval / 12)),
                    None,
                )
                if job.type == "blink_history":
                    scan = db.get(RecordingScan, history_id(job.payload["source_id"]))
                    if scan and scan.checked_at is not None:
                        job.status = "done"
            else:
                job.status, job.safe_error = "done", None
            db.commit()

    async def run(self) -> None:
        while True:
            self.last_tick = time.time()
            try:
                job = self.claim()
                if job:
                    await self.execute(job)
                    await asyncio.sleep(5)
                    continue
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=2)
                except TimeoutError:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger("porchlight").error(
                    '{"event":"recording_worker_unavailable","code":"WORKER_RETRY"}'
                )
                await asyncio.sleep(10)
