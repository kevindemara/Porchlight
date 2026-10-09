from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from porchlight.ai.frames import EXTRACTION_VERSION, REVIEWABLE_EXTRACTIONS, extract_frames
from porchlight.ai.observations import CONTRACT_DIGEST, ObservationError, validate_observation
from porchlight.ai.ollama import Ollama
from porchlight.ai.workloads import WORKLOAD_VERSION, Workload
from porchlight.api.contracts import (
    AnalysisEntity,
    AnalysisJobView,
    AnalysisStatus,
    AnalysisView,
    ApiError,
    AppSettings,
    EvidenceFrame,
    ModelTestResult,
    ModelView,
)
from porchlight.config import Config
from porchlight.notifications import plan_notifications
from porchlight.storage.database import Database
from porchlight.storage.models import (
    Analysis,
    Event,
    IntegrationState,
    Job,
    MediaAsset,
    SettingsRow,
)


class AnalysisPipeline:
    """A separate, bounded durable worker; AI failures never block clip ingestion."""

    def __init__(self, config: Config, db: Database, ollama: Ollama):
        self.config, self.db, self.ollama = config, db, ollama
        self.wake = asyncio.Event()
        self.schedule_wake = asyncio.Event()
        self.on_completed: Callable[[], None] | None = None
        with db.session() as session:
            for job in session.scalars(
                select(Job).where(Job.type == "ai_analyze", Job.status == "running")
            ):
                accepted = session.scalar(select(Analysis.id).where(Analysis.job_id == job.id))
                job.status, job.lease_until = "done" if accepted else "queued", None
                if not accepted:
                    # Interrupted work was already due; preserve unrelated queued retries.
                    job.available_at = min(job.available_at, time.time())
                event = session.get(Event, job.payload["event_id"])
                if event and not accepted:
                    event.analysis_status = "queued"
            session.commit()

    def settings(self) -> AppSettings:
        with self.db.session() as db:
            row = db.get(SettingsRow, 1)
            assert row is not None
            return AppSettings(revision=row.revision, **row.values)

    def record_test(self, tested: ModelTestResult) -> None:
        with self.db.session() as db:
            key = f"ai_test:{tested.model}"
            row = db.get(IntegrationState, key)
            if not row:
                row = IntegrationState(id=key, values={})
                db.add(row)
            row.values = {"passed": tested.passed, "digest": tested.digest}
            db.commit()

    async def ready_model(self, name: str | None) -> ModelView:
        selected = await self.ollama.private_model(name)
        with self.db.session() as db:
            row = db.get(IntegrationState, f"ai_test:{name}")
            if (
                not row
                or not row.values.get("passed")
                or row.values.get("digest") != selected.digest
            ):
                raise ApiError(409, "MODEL_TEST_REQUIRED", "Run the synthetic image test first.")
        if not self.config.tool_path("ffmpeg"):
            raise ApiError(409, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg before analysis.")
        return selected

    async def view(self) -> AnalysisStatus:
        settings = self.settings()
        disabled = await self.ollama.cloud_disabled()
        ready, message = False, "Select and test a local vision model."
        if not disabled:
            message = "Ollama must disable cloud features before private clip analysis."
        elif settings.ai_model:
            try:
                await self.ready_model(settings.ai_model)
                ready, message = (
                    True,
                    "Local analysis is ready. Older clips are analyzed on request.",
                )
            except ApiError as error:
                message = error.message
        with self.db.session() as db:
            counts = dict(
                db.execute(
                    select(Job.status, func.count())
                    .where(Job.type == "ai_analyze")
                    .group_by(Job.status)
                ).all()
            )
        return AnalysisStatus(
            enabled=settings.ai_enabled,
            ready=ready,
            cloud_disabled=disabled,
            model=settings.ai_model,
            message=message,
            queued=counts.get("queued", 0),
            running=counts.get("running", 0),
            completed=counts.get("done", 0),
            failed=counts.get("failed", 0) + counts.get("blocked", 0),
        )

    def latest(self, event_id: str) -> AnalysisView | None:
        with self.db.session() as db:
            row = db.scalar(
                select(Analysis)
                .where(Analysis.event_id == event_id)
                .order_by(Analysis.revision.desc())
                .limit(1)
            )
            return (
                AnalysisView(
                    revision=row.revision,
                    model=row.model,
                    model_digest=row.model_digest,
                    created_at=row.created_at,
                    elapsed_seconds=row.elapsed_seconds,
                    frame_count=len(row.frames),
                    workload=row.frames[0].get("workload", "balanced")
                    if row.frames
                    else "balanced",
                    uncertainty=row.observation["uncertainty"],
                    entities=[
                        AnalysisEntity(
                            **{
                                key: entity[key]
                                for key in ("category", "subtype", "color", "actions", "direction")
                            }
                        )
                        for entity in row.observation["entities"]
                    ],
                    sample_offsets_ms=[int(frame["offset_ms"]) for frame in row.frames],
                    evidence_frames=[
                        EvidenceFrame(frame_id=frame["frame_id"], offset_ms=frame["offset_ms"])
                        for frame in row.frames
                        if frame.get("extraction_version") in REVIEWABLE_EXTRACTIONS
                    ],
                    scene_visibility=row.observation["scene_visibility"],
                )
                if row
                else None
            )

    def enqueue(
        self, event_id: str, model: ModelView, *, automatic: bool, reanalyze: bool = False
    ) -> AnalysisJobView:
        now = time.time()
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            event = db.get(Event, event_id)
            if not event:
                raise ApiError(404, "EVENT_NOT_FOUND", "This recording is unavailable.")
            if automatic and event.historical:
                raise ApiError(
                    409, "AI_HISTORY_MANUAL_REQUIRED", "Analyze historical imports manually."
                )
            active = next(
                (
                    j
                    for j in db.scalars(
                        select(Job).where(
                            Job.type == "ai_analyze", Job.status.in_(["queued", "running"])
                        )
                    )
                    if j.payload.get("event_id") == event_id
                ),
                None,
            )
            if active:
                if not automatic and active.status == "queued":
                    active.payload = {**active.payload, "automatic": False}
                    db.commit()
                    self.wake.set()
                return AnalysisJobView(job_id=active.id, status=active.status)
            workload = self.settings().ai_workload
            key = (
                f"analysis:{event_id}:{model.digest}:{CONTRACT_DIGEST}:"
                f"{EXTRACTION_VERSION}:{WORKLOAD_VERSION}:{workload}"
            )
            existing = db.scalar(
                select(Job)
                .where(Job.type == "ai_analyze", Job.dedup_key.startswith(key))
                .order_by(Job.available_at.desc())
                .limit(1)
            )
            if existing and existing.status == "done" and not reanalyze:
                return AnalysisJobView(job_id=existing.id, status=existing.status)
            count = (
                db.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(Job.type == "ai_analyze", Job.status.in_(["queued", "running"]))
                )
                or 0
            )
            if count >= 100:
                raise ApiError(409, "AI_BACKLOG_FULL", "The analysis queue is full. Try later.")
            if existing and not reanalyze:
                existing.status, existing.attempt, existing.available_at, existing.safe_error = (
                    "queued",
                    0,
                    now,
                    None,
                )
                existing.payload = {
                    **existing.payload,
                    "automatic": automatic,
                    "workload": workload,
                    "contract": CONTRACT_DIGEST,
                    "extraction_version": EXTRACTION_VERSION,
                    "workload_version": WORKLOAD_VERSION,
                }
                job = existing
            else:
                job = Job(
                    id=str(uuid4()),
                    type="ai_analyze",
                    dedup_key=key if not existing else f"{key}:{uuid4()}",
                    payload={
                        "event_id": event_id,
                        "model": model.name,
                        "digest": model.digest,
                        "automatic": automatic,
                        "workload": workload,
                        "contract": CONTRACT_DIGEST,
                        "extraction_version": EXTRACTION_VERSION,
                        "workload_version": WORKLOAD_VERSION,
                    },
                    status="queued",
                    attempt=0,
                    available_at=now,
                    lease_until=None,
                    safe_error=None,
                )
                db.add(job)
            event.analysis_status = "queued"
            db.commit()
            result = AnalysisJobView(job_id=job.id, status=job.status)
        self.wake.set()
        return result

    async def request(self, event_id: str, reanalyze: bool) -> AnalysisJobView:
        settings = self.settings()
        model = await self.ready_model(settings.ai_model)
        return self.enqueue(event_id, model, automatic=False, reanalyze=reanalyze)

    async def schedule_new(self) -> None:
        settings = self.settings()
        if not settings.ai_enabled:
            return
        model = await self.ready_model(settings.ai_model)
        with self.db.session() as db:
            control = db.get(IntegrationState, "ai_control")
            enabled_at = control.values.get("enabled_at") if control else None
            if not isinstance(enabled_at, str):
                return
            recent = datetime.fromtimestamp(time.time() - 86400, UTC).isoformat()
            ids = list(
                db.scalars(
                    select(Event.id)
                    .where(
                        Event.discovered_at >= enabled_at,
                        Event.analysis_status == "not_analyzed",
                        Event.source_type.in_(["blink_cloud", "blink_local"]),
                        Event.historical.is_(False),
                        Event.captured_at >= recent,
                    )
                    .order_by(Event.captured_at.desc())
                    .limit(100)
                )
            )
        for event_id in ids:
            try:
                self.enqueue(event_id, model, automatic=True)
            except ApiError as error:
                if error.code == "AI_BACKLOG_FULL":
                    break
                raise

    def claim(self) -> Job | None:
        automatic_enabled = self.settings().ai_enabled
        now = time.time()
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            candidates = list(
                db.scalars(
                    select(Job).where(
                        Job.type == "ai_analyze", Job.status == "queued", Job.available_at <= now
                    )
                )
            )
            candidates.sort(key=lambda j: (not bool(j.payload.get("automatic")), -j.available_at))
            if not automatic_enabled:
                candidates = [job for job in candidates if not job.payload.get("automatic")]
            job = candidates[0] if candidates else None
            if job:
                event = db.get(Event, job.payload["event_id"])
                if (
                    job.payload.get("automatic")
                    and event
                    and (
                        event.historical
                        or event.captured_at is None
                        or event.captured_at < datetime.fromtimestamp(now - 86400, UTC).isoformat()
                    )
                ):
                    job.status, job.safe_error = "expired", "AI_BACKFILL_EXPIRED"
                    event.analysis_status = "not_analyzed"
                    db.commit()
                    return None
                job.status, job.attempt, job.lease_until = "running", job.attempt + 1, now + 240
                if event:
                    event.analysis_status = "analyzing"
                db.commit()
            return job

    async def analyze_job(self, job: Job) -> None:
        with self.db.session() as db:
            if db.scalar(select(Analysis.id).where(Analysis.job_id == job.id)):
                return
            event = db.get(Event, job.payload["event_id"])
            asset = db.get(MediaAsset, event.media_id) if event else None
            if not event or not asset:
                raise ApiError(404, "MEDIA_NOT_FOUND", "The saved recording is unavailable.")
            path = self.config.data_root / asset.relative_path
            duration, sha = asset.duration_seconds, asset.sha256
            media_type = asset.media_type
        if not path.resolve().is_relative_to((self.config.data_root / "media").resolve()):
            raise ApiError(404, "MEDIA_NOT_FOUND", "The saved recording is unavailable.")

        def checksum(media: Path) -> str:
            if not media.is_file() or media.stat().st_size > 256 * 1024**2:
                raise ApiError(404, "MEDIA_NOT_FOUND", "The saved recording is unavailable.")
            with media.open("rb") as handle:
                return hashlib.file_digest(handle, "sha256").hexdigest()

        if await asyncio.to_thread(checksum, path) != sha:
            raise ApiError(
                422, "MEDIA_CHANGED", "The recording no longer matches its saved checksum."
            )
        model = await self.ready_model(job.payload["model"])
        if self.settings().ai_model != model.name:
            raise ApiError(
                409, "MODEL_CHANGED", "The selected model changed. Request analysis again."
            )
        if model.digest != job.payload["digest"]:
            raise ApiError(409, "MODEL_CHANGED", "The model changed. Test it again first.")
        workload: Workload = job.payload.get("workload", "balanced")
        expected = (
            f"analysis:{job.payload['event_id']}:{model.digest}:{CONTRACT_DIGEST}:"
            f"{EXTRACTION_VERSION}:{WORKLOAD_VERSION}:{workload}"
        )
        versions = {
            "contract": CONTRACT_DIGEST,
            "extraction_version": EXTRACTION_VERSION,
            "workload_version": WORKLOAD_VERSION,
        }
        if any(job.payload.get(key, value) != value for key, value in versions.items()) or (
            job.dedup_key != expected and not job.dedup_key.startswith(expected + ":")
        ):
            raise ApiError(
                409,
                "ANALYSIS_CONTRACT_CHANGED",
                "The analysis contract changed with an app update. Request analysis again.",
            )
        started = time.monotonic()
        frames = await extract_frames(path, duration, self.config, media_type, workload)
        if job.payload.get("automatic") and not self.settings().ai_enabled:
            raise ApiError(409, "AI_PAUSED", "Automatic analysis was paused.")
        observation, summary = validate_observation(
            await self.ollama.analyze(model, frames, workload), frames
        )
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "asset": sha,
                    "model": model.digest,
                    "contract": CONTRACT_DIGEST,
                    "workload": workload,
                    "workload_version": WORKLOAD_VERSION,
                    "frames": [frame.evidence() for frame in frames],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            if db.scalar(select(Analysis.id).where(Analysis.job_id == job.id)):
                return
            event = db.get(Event, job.payload["event_id"])
            assert event is not None
            revision = (
                db.scalar(select(func.max(Analysis.revision)).where(Analysis.event_id == event.id))
                or 0
            ) + 1
            db.add(
                Analysis(
                    id=str(uuid4()),
                    event_id=event.id,
                    job_id=job.id,
                    revision=revision,
                    model=model.name,
                    model_digest=model.digest,
                    contract_digest=CONTRACT_DIGEST,
                    input_fingerprint=fingerprint,
                    frames=[frame.evidence() for frame in frames],
                    observation=observation,
                    elapsed_seconds=round(time.monotonic() - started, 2),
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
            event.summary, event.analysis_status = summary, "analyzed"
            if job.payload.get("automatic"):
                db.flush()
                plan_notifications(db, event, analyzed=True)
            db.commit()

    async def execute(self, claimed: Job) -> None:
        error: ApiError | None = None
        try:
            async with asyncio.timeout(210):
                await self.analyze_job(claimed)
                if claimed.payload.get("automatic") and self.on_completed:
                    self.on_completed()
        except ApiError as exc:
            error = exc
        except Exception:
            error = ApiError(503, "ANALYSIS_FAILED", "Analysis could not complete.", True)
        with self.db.session() as db:
            job = db.get(Job, claimed.id)
            assert job is not None
            job.lease_until = None
            if error:
                if isinstance(error, ObservationError):
                    job.payload = {**job.payload, "validation_reason": error.safe_reason}
                # At most one retry, including malformed output; no private output in errors.
                retry = (error.retryable or error.code == "ANALYSIS_INVALID") and job.attempt < 2
                job.status = "queued" if retry else "blocked" if error.status == 409 else "failed"
                job.available_at, job.safe_error = time.time() + 120, error.code
                event = db.get(Event, job.payload["event_id"])
                if event:
                    event.analysis_status = "queued" if retry else "analysis_failed"
            else:
                job.status, job.safe_error = "done", None
            db.commit()

    def notify_recording(self) -> None:
        """Coalesce archive/settings changes without waiting on AI during ingestion."""
        self.schedule_wake.set()

    async def schedule_loop(self) -> None:
        while True:
            # Clear before scanning: arrivals during model checks request another scan.
            self.schedule_wake.clear()
            delay = 30
            try:
                await self.schedule_new()
            except ApiError:
                delay = 5
            except Exception:
                logging.getLogger("porchlight").error(
                    '{"event":"analysis_scheduler_unavailable","code":"WORKER_RETRY"}'
                )
                delay = 10
            try:
                await asyncio.wait_for(self.schedule_wake.wait(), delay)
            except TimeoutError:
                pass

    async def run(self) -> None:
        # Keep discovering durable work while the single inference worker is busy.
        # TaskGroup cancellation owns both loops; neither survives app shutdown.
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(self.schedule_loop())
            tasks.create_task(self.work_loop())

    async def work_loop(self) -> None:
        while True:
            self.last_tick = time.time()
            try:
                job = self.claim()
                if job:
                    await self.execute(job)
                    continue
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), 2)
                except TimeoutError:
                    pass
            except asyncio.CancelledError:
                raise
            except ApiError:
                await asyncio.sleep(5)
            except Exception:
                logging.getLogger("porchlight").error(
                    '{"event":"analysis_worker_unavailable","code":"WORKER_RETRY"}'
                )
                await asyncio.sleep(10)
