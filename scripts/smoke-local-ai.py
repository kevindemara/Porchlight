"""Opt-in native Ollama check using generated pixels in an isolated temporary profile."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from porchlight.ai.ollama import Ollama
from porchlight.ai.pipeline import AnalysisPipeline
from porchlight.api.contracts import AppSettings
from porchlight.config import Config
from porchlight.ingestion.imports import Importer
from porchlight.storage.database import Database
from porchlight.storage.models import Analysis, Event, Job, SettingsRow
from sqlalchemy import func, select


async def check(model_name: str, root: Path) -> None:
    config = Config(data_root=root)
    db, ollama = Database(root), Ollama(config)
    try:
        db.migrate()
        model = await ollama.private_model(model_name)
        tested = await ollama.smoke_test(model_name)
        if not tested.passed:
            raise RuntimeError("Generated two-colour image check failed")
        with db.session() as session:
            session.add(
                SettingsRow(
                    id=1,
                    revision=1,
                    values=AppSettings(revision=1, ai_enabled=True, ai_model=model_name).model_dump(
                        exclude={"revision"}
                    ),
                )
            )
            session.commit()
        importer = Importer(config, db)
        temporary = importer.media / "generated.mp4"
        executable = config.tool_path("ffmpeg")
        if not executable:
            raise RuntimeError("FFmpeg is required")
        subprocess.run(
            [
                executable,
                "-v",
                "error",
                "-nostdin",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=320x240:d=1,drawbox=x=160:y=0:w=160:h=240:color=blue:t=fill",
                "-c:v",
                "mpeg4",
                "-y",
                str(temporary),
            ],
            check=True,
            timeout=30,
        )
        video = temporary.read_bytes()
        sha = hashlib.sha256(video).hexdigest()
        temporary.rename(importer.media / f"{sha}.mp4")
        event_id = importer.commit_import(
            {
                "sha256": sha,
                "source_key": "synthetic:native-smoke",
                "bytes": len(video),
                "captured_at": None,
                "discovered_at": datetime.now(UTC).isoformat(),
                "source_type": "manual_import",
                "duration_seconds": 1,
                "width": 320,
                "height": 240,
            }
        )
        pipeline = AnalysisPipeline(config, db, ollama)
        pipeline.record_test(tested)
        pipeline.enqueue(event_id, model, automatic=False)
        job = pipeline.claim()
        assert job
        await pipeline.execute(job)
        with db.session() as session:
            completed = session.get(Job, job.id)
            event = session.get(Event, event_id)
            accepted = session.scalar(select(func.count()).select_from(Analysis))
            assert completed and event
            result = {
                "synthetic_only": True,
                "cloud_disabled": await ollama.cloud_disabled(),
                "model": model.name,
                "digest": model.digest,
                "image_test_passed": tested.passed,
                "image_test_seconds": tested.elapsed_seconds,
                "job_status": completed.status,
                "safe_error": completed.safe_error,
                "accepted_analyses": accepted,
                "summary": event.summary,
            }
        latest = pipeline.latest(event_id)
        if latest:
            result.update(frame_count=latest.frame_count, analysis_seconds=latest.elapsed_seconds)
        print(json.dumps(result, indent=2))
        if completed.status != "done" or accepted != 1:
            raise RuntimeError("Generated clip analysis did not complete")
    finally:
        await ollama.close()
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="An already installed local vision alias")
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="porchlight-native-ai-") as directory:
        asyncio.run(check(arguments.model, Path(directory)))
