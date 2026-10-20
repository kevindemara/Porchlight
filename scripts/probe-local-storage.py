"""Owner-run, single-actor storage check. Never prints identities, media or raw responses."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from uuid import uuid4

from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.ingestion.imports import inspect_mp4
from porchlight.providers.blink.adapter import BlinkAdapter
from porchlight.providers.blink.local_storage import LocalStorageSource
from porchlight.security.lock import InstanceLock
from porchlight.security.vault import WindowsVault
from porchlight.storage.database import Database


def storage_flags(module: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for field in ("local_storage_enabled", "local_storage_compatible"):
        value = module.get(field)
        result[field] = value if isinstance(value, bool) else None
        result[field + "_format"] = (
            "missing" if field not in module else "boolean" if isinstance(value, bool) else "other"
        )
    value = module.get("local_storage_status")
    result["local_storage_status"] = (
        value
        if isinstance(value, str)
        and value in {"active", "inactive", "disabled", "unavailable", "error", "backup"}
        else "missing"
        if "local_storage_status" not in module
        else "unrecognized"
    )
    return result


def emit(value: dict[str, object]) -> None:
    print(json.dumps(value), flush=True)


async def probe(download_latest: bool) -> None:
    config = Config()
    lock = InstanceLock(config.data_root)
    lock.acquire()  # Stop only the regular Porchlight backend before this explicit check.
    db = Database(config.data_root)
    adapter = BlinkAdapter(db, WindowsVault(config.data_root))
    try:
        async with asyncio.timeout(210):
            await adapter.restore_session()
            emit({"phase": "connection", "state": adapter.status.state})
            if adapter.status.state != "connected" or adapter.blink is None:
                return
            modules = adapter.blink.homescreen.get("sync_modules", [])
            emit(
                {
                    "phase": "storage_flags",
                    "modules": [
                        storage_flags(module) for module in modules if isinstance(module, dict)
                    ],
                    "eligible_modules": len(adapter.local_targets),
                }
            )
            if not adapter.local_targets:
                emit({"phase": "manifest_not_requested", "reason": "LOCAL_STORAGE_NOT_READY"})
                return
            source = LocalStorageSource(adapter)
            page = await source.recording_page(0, 1)
            emit({"phase": "manifest", "clip_count": len(page.clips), "complete": page.exhausted})
            if not page.clips:
                emit(
                    {
                        "phase": "no_local_clips",
                        "download_test": "not_run",
                        "no_plan_verified": False,
                    }
                )
                return
            if download_latest and page.clips:
                clip = max(page.clips, key=lambda item: item.captured_at or "")
                directory = config.data_root / "private-reports" / "local-storage"
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"{uuid4()}.mp4"
                await source.download_recording(clip.media_path, path)
                details = await inspect_mp4(path, config)
                emit(
                    {
                        "phase": "download_validated",
                        "bytes": path.stat().st_size,
                        "duration_seconds": details["duration_seconds"],
                        "saved_outside_repository": True,
                        "no_plan_verified": False,
                    }
                )
    finally:
        await adapter.close()
        db.close()
        lock.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-latest", action="store_true")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)  # Upstream diagnostics can contain tokens or raw responses.
    try:
        asyncio.run(probe(args.download_latest))
    except ApiError as error:
        emit({"phase": "failed", "code": error.code})
        raise SystemExit(1) from None
    except Exception:
        emit({"phase": "failed", "code": "LOCAL_PROBE_FAILED"})
        raise SystemExit(1) from None
