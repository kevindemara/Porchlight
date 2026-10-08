"""Bounded local backfill for saved Activity items without face reports.

Prints aggregate counts only. Existing accepted reports and owner labels stay intact.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter

from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.faces.pipeline import FacePipeline
from porchlight.storage.database import Database
from porchlight.storage.models import Event, FaceDetection, Job, MediaAsset
from sqlalchemy import func, select


def active_count(db: Database) -> int:
    with db.session() as session:
        return session.scalar(
            select(func.count()).select_from(Job).where(
                Job.type == "face_detect", Job.status.in_(["queued", "running"])
            )
        ) or 0


def report_count(db: Database, event_ids: list[str]) -> int:
    if not event_ids:
        return 0
    with db.session() as session:
        return session.scalar(
            select(func.count()).select_from(FaceDetection).where(
                FaceDetection.event_id.in_(event_ids)
            )
        ) or 0


def emit(**values: object) -> None:
    print(json.dumps(values, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Start the bounded local backfill")
    args = parser.parse_args()
    config = Config()
    db = Database(config.data_root)
    try:
        with db.session() as session:
            all_ids = list(session.scalars(
                select(Event.id).join(MediaAsset, Event.media_id == MediaAsset.id)
                .order_by(func.coalesce(Event.captured_at, Event.discovered_at).desc())
            ))
            existing = set(session.scalars(select(FaceDetection.event_id)))
        missing = [event_id for event_id in all_ids if event_id not in existing]
        emit(saved_items=len(all_ids), accepted_reports=len(existing), missing=len(missing))
        if not args.run or not missing:
            return 0
        if active_count(db):
            emit(error="face_jobs_already_active", active=active_count(db))
            return 2
        pipeline = FacePipeline(config, db)
        pipeline.ready()
        submitted = 0
        for event_id in missing:
            while active_count(db) >= 24:
                time.sleep(2)
            try:
                pipeline.enqueue(event_id, reanalyze=True)
            except ApiError as exc:
                if exc.code != "FACE_QUEUE_FULL":
                    raise
                while active_count(db) >= 24:
                    time.sleep(2)
                pipeline.enqueue(event_id, reanalyze=True)
            submitted += 1
            if submitted % 10 == 0 or submitted == len(missing):
                emit(submitted=submitted, total=len(missing),
                     completed=report_count(db, missing), active=active_count(db))
        while active_count(db):
            time.sleep(5)
            emit(submitted=submitted, total=len(missing),
                 completed=report_count(db, missing), active=active_count(db))
        completed = report_count(db, missing)
        if completed != len(missing):
            with db.session() as session:
                failed = Counter(session.scalars(
                    select(Job.safe_error).where(Job.type == "face_detect", Job.status == "failed")
                ))
            emit(completed=completed, missing=len(missing) - completed,
                 failure_codes={str(key): value for key, value in failed.items()})
            return 1
        emit(completed=completed, total=len(missing), active=0)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
