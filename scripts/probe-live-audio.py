"""Owner-triggered local audio-track inspection; never exports or saves private media."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import suppress

from porchlight.config import Config
from porchlight.providers.blink.adapter import BlinkAdapter
from porchlight.security.lock import InstanceLock
from porchlight.security.vault import WindowsVault
from porchlight.storage.database import Database


async def probe() -> bool:
    config = Config()
    executable = config.tool_path("ffprobe")
    if not executable:
        print(json.dumps({"passed": False, "safe_code": "MEDIA_TOOLS_REQUIRED"}))
        return False
    lock = InstanceLock(config.data_root)
    lock.acquire()
    db = Database(config.data_root)
    adapter = BlinkAdapter(db, WindowsVault(config.data_root))
    try:
        await adapter.restore_session()
        if len(adapter.cameras) != 1:
            raise ValueError("Choose a camera locally before probing")
        source = await adapter.open_live(adapter.cameras[0].id)
        data = bytearray()
        try:
            with suppress(TimeoutError):
                async with asyncio.timeout(6):
                    while chunk := await source.read():
                        data.extend(chunk)
                        if len(data) >= 2 * 1024**2:
                            break
        finally:
            await source.close()
        process = await asyncio.create_subprocess_exec(
            executable,
            "-v",
            "error",
            "-protocol_whitelist",
            "pipe",
            "-f",
            "mpegts",
            "-show_entries",
            "stream=codec_type,codec_name",
            "-of",
            "json",
            "pipe:0",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(bytes(data)), 10)
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()
        details = json.loads(output)
        streams = details.get("streams", [])
        audio = [s for s in streams if s.get("codec_type") == "audio"]
        codecs = {"aac", "pcm_alaw", "pcm_mulaw", "mp2", "mp3", "opus"}
        print(
            json.dumps(
                {
                    "real_camera": True,
                    "sample_bytes": len(data),
                    "video_tracks": sum(s.get("codec_type") == "video" for s in streams),
                    "audio_tracks": len(audio),
                    "audio_codecs": [
                        s.get("codec_name") if s.get("codec_name") in codecs else "other"
                        for s in audio
                    ],
                    "media_saved": False,
                    "audible_content_verified": False,
                }
            )
        )
        return process.returncode == 0 and bool(streams)
    finally:
        await adapter.close()
        db.close()
        lock.release()


if __name__ == "__main__":
    try:
        passed = asyncio.run(probe())
    except Exception:
        print(json.dumps({"passed": False, "safe_code": "AUDIO_PROBE_UNAVAILABLE"}))
        passed = False
    sys.exit(0 if passed else 1)
