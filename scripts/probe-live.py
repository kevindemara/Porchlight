"""Explicit short hardware probe; emits only safe stream counts, never imagery or relay URLs."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from contextlib import suppress

from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.live import LiveViews
from porchlight.providers.blink.adapter import BlinkAdapter
from porchlight.security.lock import InstanceLock
from porchlight.security.vault import WindowsVault
from porchlight.storage.database import Database


async def probe(approval: str | None = None, repeat: int = 1) -> bool:
    config = Config()
    lock = InstanceLock(config.data_root)
    lock.acquire()  # The regular app must be stopped; never run two account actors.
    db = Database(config.data_root)
    adapter = BlinkAdapter(db, WindowsVault(config.data_root))
    manager = LiveViews(config, adapter)
    started = time.monotonic()
    try:
        await adapter.restore_session()
        if len(adapter.cameras) != 1:
            raise ApiError(409, "PROBE_CAMERA_SELECTION", "This probe requires exactly one camera.")
        camera = adapter.cameras[0]
        if camera.id not in adapter.live_cameras:
            raise ApiError(409, "LIVE_UNSUPPORTED", "The camera has no supported live descriptor.")
        successful = True
        for attempt in range(1, repeat + 1):
            if attempt > 1:
                print(json.dumps({"phase": "reconnecting"}), flush=True)
            successful = await sample(manager, adapter, approval, attempt, started) and successful
        return successful
    finally:
        await manager.stop()
        await adapter.close()
        db.close()
        lock.release()


async def sample(
    manager: LiveViews, adapter: BlinkAdapter, approval: str | None, attempt: int, started: float
) -> bool:
    heartbeat: asyncio.Task[None] | None = None
    try:
        camera = adapter.cameras[0]
        view = await manager.start(camera.id, "local-hardware-probe")
        current = manager.require(view.id, "local-hardware-probe")

        async def touch() -> None:
            while True:
                manager.touch(view.id, "local-hardware-probe")
                await asyncio.sleep(2)

        heartbeat = asyncio.create_task(touch())
        captured = bytearray()
        sample_arrived = False
        async with asyncio.timeout(35):
            async for chunk in manager.media(current):
                captured.extend(chunk)
                if b"moof" in captured and b"mdat" in captured:
                    sample_arrived = True
                    break
                if len(captured) > 2 * 1024**2:
                    break
        status = manager.view(current)
        certificate_approved = False
        if approval and status.certificate_sha256 == approval:
            adapter.trust_live_certificate(approval)
            certificate_approved = True
        print(
            json.dumps(
                {
                    "real_camera": True,
                    "attempt": attempt,
                    "camera_count": len(adapter.cameras),
                    "video_sample_arrived": sample_arrived,
                    "encoded_bytes": status.bytes_received,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "state": status.state,
                    "audio_status": status.audio_status,
                    "safe_message": status.message,
                    "imagery_saved": False,
                    "browser_playback_verified": False,
                    "certificate_sha256": status.certificate_sha256,
                    "certificate_approved": certificate_approved,
                },
                indent=2,
            )
        )
        return sample_arrived or certificate_approved
    finally:
        if heartbeat:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
        cleanup_started = time.monotonic()
        await manager.stop()
        print(
            json.dumps(
                {
                    "attempt": attempt,
                    "phase": "local_cleanup_complete",
                    "cleanup_seconds": round(time.monotonic() - cleanup_started, 2),
                    "remote_camera_released_verified": False,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("porchlight.providers.blink.live").setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repeat",
        type=int,
        choices=(1, 2),
        default=1,
        help="Run two consecutive short connections to check reconnect cleanup",
    )
    parser.add_argument(
        "--approve-certificate",
        help="Explicitly approve this exact observed SHA-256 fingerprint for Porchlight",
    )
    args = parser.parse_args()
    try:
        passed = asyncio.run(probe(args.approve_certificate, args.repeat))
    except ApiError as error:
        print(json.dumps({"passed": False, "safe_code": error.code, "safe_message": error.message}))
        passed = False
    except Exception:
        print(json.dumps({"passed": False, "safe_code": "PROBE_UNAVAILABLE"}))
        passed = False
    sys.exit(0 if passed else 1)
