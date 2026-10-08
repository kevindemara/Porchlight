"""One-clip local AI test; outputs validated fields and safe metrics, never imagery."""

from __future__ import annotations

import argparse
import asyncio
import json
import time

from porchlight.ai.observations import VALIDATION_REASONS
from porchlight.ai.ollama import Ollama
from porchlight.ai.pipeline import AnalysisPipeline
from porchlight.ai.workloads import Workload
from porchlight.api.contracts import ApiError, AppSettings
from porchlight.config import Config
from porchlight.security.lock import InstanceLock
from porchlight.storage.database import Database
from porchlight.storage.models import Analysis, Event, IntegrationState, Job, MediaAsset
from sqlalchemy import func, select


class OneClipPipeline(AnalysisPipeline):
    """Opt into this clip in memory while preserving persisted automatic-AI settings."""

    model_name: str
    workload: Workload = "balanced"

    def settings(self) -> AppSettings:
        return (
            super()
            .settings()
            .model_copy(
                update={
                    "ai_enabled": True,
                    "ai_model": self.model_name,
                    "ai_workload": self.workload,
                }
            )
        )


async def check(model_name: str, offset: int = 0, workload: Workload = "balanced") -> bool:
    config = Config()
    lock = InstanceLock(config.data_root)
    lock.acquire()  # Stop the normal app first; no duplicate workers or account actors.
    db, ollama = Database(config.data_root), Ollama(config)
    started = time.monotonic()
    try:
        db.migrate()
        with db.session() as session:
            inventory = session.get(IntegrationState, "blink")
            camera_ids = (
                [camera["id"] for camera in inventory.values.get("cameras", [])]
                if inventory
                else []
            )
            event = session.scalar(
                select(Event)
                .join(MediaAsset, Event.media_id == MediaAsset.id)
                .where(Event.source_type == "blink_cloud", Event.camera_id.in_(camera_ids))
                .order_by(
                    func.coalesce(Event.captured_at, Event.discovered_at).desc(), Event.id.desc()
                )
                .limit(1)
                .offset(offset)
            )
            if event is None:
                raise ApiError(
                    404, "NO_CAMERA_RECORDING", "No archived camera recording is available."
                )
            event_id = event.id
        pipeline = OneClipPipeline(config, db, ollama)
        pipeline.model_name = model_name
        pipeline.workload = workload
        try:
            model = await pipeline.ready_model(model_name)
        except ApiError as error:
            if error.code != "MODEL_TEST_REQUIRED":
                raise
            tested = await ollama.smoke_test(model_name)
            pipeline.record_test(tested)
            if not tested.passed:
                raise ApiError(
                    409, "MODEL_TEST_REQUIRED", "The synthetic image test did not pass."
                ) from error
            model = await pipeline.ready_model(model_name)
        queued = pipeline.enqueue(event_id, model, automatic=False, reanalyze=True)
        with db.session() as session:
            job = session.get(Job, queued.job_id)
            assert job is not None
            job.status, job.attempt, job.lease_until = "running", 1, time.time() + 240
            current = session.get(Event, event_id)
            assert current is not None
            current.analysis_status = "analyzing"
            session.commit()
        await pipeline.execute(job)
        with db.session() as session:
            completed = session.get(Job, queued.job_id)
            assert completed is not None
            # This manual probe makes exactly one attempt; it never leaves a silent retry behind.
            if completed.status == "queued":
                completed.status = "failed"
                failed = session.get(Event, event_id)
                assert failed is not None
                failed.analysis_status = "analysis_failed"
                session.commit()
            accepted = session.scalar(select(Analysis).where(Analysis.job_id == queued.job_id))
            result = {
                "real_camera_clip": True,
                "one_clip_only": True,
                "recent_clip_offset": offset,
                "workload": workload,
                "cloud_disabled": await ollama.cloud_disabled(),
                "model": model_name,
                "status": completed.status,
                "safe_error": completed.safe_error,
                "validation_reason": completed.payload.get("validation_reason")
                if completed.payload.get("validation_reason") in VALIDATION_REASONS
                else None,
                "total_seconds": round(time.monotonic() - started, 2),
                "imagery_sent_to_coding_tools": False,
                "automatic_ai_setting_changed": False,
            }
            if accepted:
                observation = accepted.observation
                result.update(
                    summary=observation["summary_suggestion"],
                    scene_visibility=observation["scene_visibility"],
                    frame_count=len(accepted.frames),
                    analysis_seconds=accepted.elapsed_seconds,
                    uncertainty=observation["uncertainty"],
                    entities=[
                        {
                            key: entity[key]
                            for key in ("category", "subtype", "color", "actions", "direction")
                        }
                        for entity in observation["entities"]
                    ],
                )
            print(json.dumps(result, indent=2))
            return accepted is not None and completed.status == "done"
    finally:
        await ollama.close()
        db.close()
        lock.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", choices=["balanced", "light"], default="balanced")
    parser.add_argument("--model", required=True, help="An already installed local vision model")
    parser.add_argument(
        "--offset",
        type=int,
        choices=range(20),
        default=0,
        help="Newest saved camera clip is 0; select another recent clip explicitly.",
    )
    args = parser.parse_args()
    try:
        passed = asyncio.run(check(args.model, args.offset, args.workload))
    except ApiError as error:
        print(json.dumps({"passed": False, "safe_code": error.code, "safe_message": error.message}))
        passed = False
    except Exception:
        print(json.dumps({"passed": False, "safe_code": "LOCAL_AI_PROBE_UNAVAILABLE"}))
        passed = False
    raise SystemExit(0 if passed else 1)
