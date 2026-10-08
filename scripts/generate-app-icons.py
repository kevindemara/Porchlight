"""Publish the approved mark and export standard browser icon sizes with existing FFmpeg."""

import shutil
import struct
import subprocess
from pathlib import Path

from porchlight.config import Config

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    source = root / "assets/brand/porchlight-logomark-concept-v3.png"
    header = source.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", header[16:24]) != (1254, 1254):
        raise ValueError("Expected the approved 1254x1254 PNG mark.")
    ffmpeg = Config().tool_path("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Configure existing FFmpeg before exporting app icons.")
    destination = root / "apps/web/public/icons"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination / "porchlight-mark-v3.png")
    for name, filters in (
        ("porchlight-v3-192.png", "scale=192:192:flags=lanczos"),
        ("porchlight-v3-512.png", "scale=512:512:flags=lanczos"),
        # The entire artwork square fits inside the central 80%-diameter safe circle.
        (
            "porchlight-v3-maskable-512.png",
            "scale=286:286:flags=lanczos,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x17201e",
        ),
    ):
        subprocess.run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                "-vf", filters, "-frames:v", "1", "-update", "1", str(destination / name),
            ],
            check=True,
            timeout=30,
        )
