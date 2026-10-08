"""Explicit one-clip local probe. Emits aggregate metrics only, never frames or paths."""

import asyncio
import json

from porchlight.config import Config
from porchlight.faces.pipeline import FacePipeline
from porchlight.security.lock import InstanceLock
from porchlight.storage.database import Database
from porchlight.storage.models import Event, IntegrationState, Job
from sqlalchemy import func, select


async def main() -> None:
    config = Config()
    lock = InstanceLock(config.data_root)
    lock.acquire()  # Stop the application first; never race its profile or workers.
    db = Database(config.data_root)
    try:
        db.migrate()
        with db.session() as session:
            inventory = session.get(IntegrationState, "blink")
            cameras = (
                [camera["id"] for camera in inventory.values.get("cameras", [])]
                if inventory
                else []
            )
            event_id = session.scalar(
                select(Event.id)
                .where(
                    Event.source_type.in_(["blink_cloud", "blink_local"]),
                    Event.camera_id.in_(cameras),
                )
                .order_by(func.coalesce(Event.captured_at, Event.discovered_at).desc())
                .limit(1)
            )
        if not event_id:
            raise RuntimeError("No recording from the connected camera is available.")
        pipeline = FacePipeline(config, db)
        pipeline.enqueue(event_id, reanalyze=True)
        # Claim only this explicit request; leave every unrelated job untouched.
        with db.session() as session:
            job = session.scalar(
                select(Job).where(
                    Job.type == "face_detect",
                    Job.status == "queued",
                    Job.payload["event_id"].as_string() == event_id,
                )
            )
            if not job:
                raise RuntimeError("A detector request is already running.")
            job.status, job.attempt = "running", 1
            session.commit()
        await pipeline.execute(job)
        result = pipeline.result(event_id)
        if result.status == "queued":
            # Explicit probe performs one attempt, without leaving unexpected retries.
            with db.session() as session:
                current = session.get(Job, job.id)
                assert current
                current.status = "failed"
                session.commit()
            result = pipeline.result(event_id)
        frames = result.report.frames if result.report else []
        print(
            json.dumps(
                {
                    "real_camera_clip": True,
                    "status": result.status,
                    "sampled_frames": len(frames),
                    "frames_with_faces": sum(bool(f.faces) for f in frames),
                    "peak_faces_in_sample": max((len(f.faces) for f in frames), default=0),
                    "elapsed_seconds": round(result.elapsed_seconds or 0, 2),
                    "automatic_detection_enabled": bool(pipeline.control().get("enabled")),
                    "imagery_sent_to_coding_tools": False,
                }
            )
        )
        if result.status != "done":
            raise RuntimeError("The one-clip detector test did not complete.")
    finally:
        db.close()
        lock.release()


if __name__ == "__main__":
    asyncio.run(main())
