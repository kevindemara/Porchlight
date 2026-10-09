"""Resize owner-supplied artwork with existing FFmpeg; preserve source PNGs."""

import json
import struct
import subprocess
from pathlib import Path

from porchlight.config import Config


def export(source: Path, output: Path, filters: str, ffmpeg: str) -> None:
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            filters,
            "-map_metadata",
            "-1",
            "-frames:v",
            "1",
            "-threads",
            "1",
            "-compression_level",
            "9",
            "-pred",
            "mixed",
            "-update",
            "1",
            str(output),
        ],
        check=True,
        timeout=30,
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    logo = root / "Porchlight-logomark-transparent.png"
    icon = root / "Porchlight-logomark-202B27-background.png"
    for source in (logo, icon):
        header = source.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Expected PNG artwork: {source.name}")
        width, height = struct.unpack(">II", header[16:24])
        if width != height or width < 512:
            raise ValueError(f"Expected square artwork of at least 512 px: {source.name}")
    ffmpeg = Config().tool_path("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Configure existing FFmpeg before exporting app icons.")
    destination = root / "apps/web/public/icons"
    destination.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for name, source, filters in (
        ("porchlight-mark-v4.png", logo, "scale=256:256:flags=lanczos,format=rgba"),
        # Android masks the small notification badge: keep the owner's alpha
        # silhouette, with white RGB and no background at four-times density.
        (
            "porchlight-badge-v4-96.png",
            logo,
            "scale=96:96:flags=lanczos,format=rgba,lutrgb=r=255:g=255:b=255",
        ),
        *(
            (f"porchlight-v4-{size}.png", icon, f"scale={size}:{size}:flags=lanczos,format=rgb24")
            for size in (16, 32, 48, 180, 192, 512)
        ),
        # The complete source square fits inside Android's central 80% safe circle.
        (
            "porchlight-v4-maskable-512.png",
            icon,
            "scale=286:286:flags=lanczos,format=rgb24,"
            "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x202B27",
        ),
    ):
        output = destination / name
        export(source, output, filters, str(ffmpeg))
        outputs.append(output)
    # ICO supports multiple PNG images; retain three browser/Windows tab sizes.
    sizes = (16, 32, 48)
    images = [(destination / f"porchlight-v4-{size}.png").read_bytes() for size in sizes]
    offset = 6 + 16 * len(images)
    entries = []
    for size, data in zip(sizes, images, strict=True):
        entries.append(struct.pack("<BBBBHHII", size, size, 0, 0, 1, 24, len(data), offset))
        offset += len(data)
    favicon = root / "apps/web/public/favicon-v4.ico"
    favicon.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries + images))
    outputs.append(favicon)
    print(
        json.dumps(
            {"exports": [{"name": file.name, "bytes": file.stat().st_size} for file in outputs]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
