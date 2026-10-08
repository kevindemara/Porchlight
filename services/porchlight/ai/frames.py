from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path

from porchlight.ai.workloads import Workload, preset
from porchlight.api.contracts import ApiError
from porchlight.config import Config
from porchlight.ingestion.imports import run_tool

EXTRACTION_VERSION = "uniform-up-to-six-local-change-v3"
SIGNATURE_EDGE = 48


@dataclass(frozen=True)
class Frame:
    id: str
    offset_ms: int
    sha256: str
    image: bytes
    signature: bytes
    monochrome: bool
    workload: Workload = "balanced"

    def evidence(self) -> dict[str, str | int | bool]:
        return {
            "frame_id": self.id,
            "offset_ms": self.offset_ms,
            "sha256": self.sha256,
            "monochrome": self.monochrome,
            "extraction_version": EXTRACTION_VERSION,
            "masking_policy": "none",
            "workload": self.workload,
        }

    def encoded(self) -> str:
        return base64.b64encode(self.image).decode("ascii")


async def frame_image(
    path: Path, offset_ms: int, config: Config, media_type: str, workload: Workload
) -> bytes:
    """Use the identical JPEG decoder settings for inference and evidence review."""
    executable = config.tool_path("ffmpeg")
    if not executable:
        raise ApiError(503, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg before analysis.", True)
    image = await run_tool(
        executable,
        "-v",
        "error",
        "-nostdin",
        "-threads",
        "2",
        "-protocol_whitelist",
        "file,pipe",
        "-ss",
        f"{offset_ms / 1000:.3f}",
        "-f",
        "mjpeg" if media_type == "image/jpeg" else "mov",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-an",
        "-frames:v",
        "1",
        "-vf",
        f"scale={preset(workload).image_edge}:{preset(workload).image_edge}:force_original_aspect_ratio=decrease",
        "-c:v",
        "mjpeg",
        "-q:v",
        "3",
        "-f",
        "image2pipe",
        "pipe:1",
        timeout=15,
    )
    if not image.startswith(b"\xff\xd8") or len(image) > 8 * 1024**2:
        raise ApiError(422, "FRAME_LIMIT", "The recording exceeds the image analysis budget.")
    return image


def similar(left: bytes, right: bytes) -> bool:
    # Whole-image averages can hide a visitor moving against an unchanged background.
    # Keep samples with a localized change. This is still scene deduplication, not tracking.
    if len(left) != len(right) or not left:
        return False
    differences = [abs(a - b) for a, b in zip(left, right, strict=True)]
    if sum(differences) / len(differences) >= 2 or max(differences) >= 24:
        return False
    if len(differences) == SIGNATURE_EDGE * SIGNATURE_EDGE * 3:
        for y in range(0, SIGNATURE_EDGE, 4):
            for x in range(0, SIGNATURE_EDGE, 4):
                patch = sum(
                    sum(
                        differences[
                            (row * SIGNATURE_EDGE + x) * 3 : (row * SIGNATURE_EDGE + x + 4) * 3
                        ]
                    )
                    for row in range(y, y + 4)
                )
                if patch / (4 * 4 * 3) >= 4:
                    return False
    return True


async def extract_frames(
    path: Path,
    duration: float,
    config: Config,
    media_type: str = "video/mp4",
    workload: Workload = "balanced",
) -> list[Frame]:
    policy = preset(workload)
    executable = config.tool_path("ffmpeg")
    if not executable:
        raise ApiError(503, "MEDIA_TOOLS_REQUIRED", "Configure FFmpeg before analysis.", True)
    if (
        not path.is_file()
        or not path.resolve().is_relative_to((config.data_root / "media").resolve())
        or not (media_type == "image/jpeg" and duration == 0 or 0 < duration <= 300)
    ):
        raise ApiError(404, "MEDIA_NOT_FOUND", "The saved recording is unavailable.")
    frames: list[Frame] = []
    total = 0
    for index in range(1 if media_type == "image/jpeg" else policy.frames):
        offset = min(duration * index / (policy.frames - 1), max(0, duration - 0.12))
        common = (
            executable,
            "-v",
            "error",
            "-nostdin",
            "-threads",
            "2",
            "-protocol_whitelist",
            "file,pipe",
            "-ss",
            f"{offset:.3f}",
            "-f",
            "mjpeg" if media_type == "image/jpeg" else "mov",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-frames:v",
            "1",
        )
        signature = await run_tool(
            *common,
            "-vf",
            f"scale={SIGNATURE_EDGE}:{SIGNATURE_EDGE}",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        )
        if len(signature) != SIGNATURE_EDGE * SIGNATURE_EDGE * 3:
            continue
        if any(similar(frame.signature, signature) for frame in frames):
            continue
        image = await frame_image(path, round(offset * 1000), config, media_type, workload)
        total += len(image)
        if not image.startswith(b"\xff\xd8") or total > 8 * 1024**2:
            raise ApiError(422, "FRAME_LIMIT", "The recording exceeds the image analysis budget.")
        chroma = sum(
            max(signature[i : i + 3]) - min(signature[i : i + 3])
            for i in range(0, len(signature), 3)
        ) / (len(signature) / 3)
        frames.append(
            Frame(
                id=f"f{len(frames) + 1:03}",
                offset_ms=round(offset * 1000),
                sha256=hashlib.sha256(image).hexdigest(),
                image=image,
                signature=signature,
                monochrome=chroma < 5,
                workload=workload,
            )
        )
    if not frames:
        raise ApiError(422, "NO_ANALYSIS_FRAMES", "No usable images could be extracted.")
    return frames
