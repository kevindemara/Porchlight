from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from porchlight.api.contracts import ApiError
from porchlight.faces.contracts import FaceBox, FaceFrame

MANIFEST = json.loads((Path(__file__).parents[1] / "face_model.json").read_text())
POLICY = "yunet-sampled-v3"
DETECTOR_THRESHOLD = 0.8
PACKAGES = {"opencv-python-headless": "4.14.0.94", "numpy": "2.5.3"}


def check_runtime(path: Path) -> None:
    for package, version in PACKAGES.items():
        try:
            installed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed != version:
            raise ApiError(
                409, "FACE_SETUP_REQUIRED", "Install the optional pinned local detector."
            )
    if not path.is_file() or path.stat().st_size != MANIFEST["bytes"]:
        raise ApiError(409, "FACE_MODEL_REQUIRED", "Install the verified YuNet face detector.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != MANIFEST["sha256"]:
        raise ApiError(
            409, "FACE_MODEL_MISMATCH", "The detector does not match its verified digest."
        )


def sample_offsets(duration: float, image: bool = False) -> list[int]:
    if image:
        return [0]
    if not math.isfinite(duration) or not 0 < duration <= 300:
        raise ValueError("Invalid clip duration")
    end = max(0, round(duration * 1000) - 120)
    # A face may be visible for only a fraction of a second as someone turns.
    # Sample short clips at about 4 fps while keeping long clips bounded.
    count = min(48, max(1, math.ceil(duration * 4)))
    return sorted({round(end * i / (count - 1)) for i in range(count)}) if count > 1 else [0]


class Detector:
    """CPU detector with optional local SFace matching; no crops or vectors are retained."""

    def __init__(
        self,
        path: Path,
        recognizer_path: Path | None = None,
        profiles: Mapping[str, Sequence[Sequence[float]]] | None = None,
    ):
        check_runtime(path)
        self.cv: Any = importlib.import_module("cv2")
        self.np: Any = importlib.import_module("numpy")
        self.cv.setNumThreads(2)
        self.native = self.cv.FaceDetectorYN.create(
            str(path), "", (320, 320), DETECTOR_THRESHOLD, 0.3, 5000
        )
        self.profiles = profiles or {}
        self.recognizer: Any = None
        if self.profiles and recognizer_path is not None:
            from porchlight.faces.recognizer import Recognizer

            self.recognizer = Recognizer(recognizer_path)

    def detect(self, jpeg: bytes, offset_ms: int) -> FaceFrame:
        image = self.cv.imdecode(
            self.np.frombuffer(jpeg, dtype=self.np.uint8), self.cv.IMREAD_COLOR
        )
        if image is None:
            raise ValueError("Invalid evidence image")
        height, width = image.shape[:2]
        if not 0 < width <= 960 or not 0 < height <= 960:
            raise ValueError("Image budget exceeded")
        self.native.setInputSize((width, height))
        _, detections = self.native.detect(image)
        faces: list[FaceBox] = []
        if detections is not None:
            if len(detections) > 25:
                raise ValueError("Detection budget exceeded")
            for row in detections:
                x, y, w, h, score = (float(row[i]) for i in (0, 1, 2, 3, 14))
                if not all(math.isfinite(v) for v in (x, y, w, h, score)) or w <= 0 or h <= 0:
                    raise ValueError("Invalid detector geometry")
                left, top = max(0, math.floor(x)), max(0, math.floor(y))
                right, bottom = min(width, math.ceil(x + w)), min(height, math.ceil(y + h))
                if right <= left or bottom <= top or score < DETECTOR_THRESHOLD:
                    continue
                crop = image[top:bottom, left:right]
                gray = self.cv.cvtColor(crop, self.cv.COLOR_BGR2GRAY)
                sharpness = float(self.cv.Laplacian(gray, self.cv.CV_64F).var())
                small = min(right - left, bottom - top) < 48
                low_sharpness = sharpness < 80
                profile_id, match_score = None, None
                if self.recognizer is not None and not small and not low_sharpness:
                    from porchlight.faces.recognizer import best_match

                    try:
                        match = best_match(self.recognizer.extract(image, row), self.profiles)
                    except (ValueError, self.cv.error):
                        match = None
                    if match:
                        profile_id, match_score = UUID(match[0]), min(1.0, max(0.0, match[1]))
                faces.append(
                    FaceBox(
                        x=left,
                        y=top,
                        width=right - left,
                        height=bottom - top,
                        score=min(score, 1),
                        small=small,
                        low_sharpness=low_sharpness,
                        profile_id=profile_id,
                        match_score=match_score,
                    )
                )
        return FaceFrame(
            offset_ms=offset_ms,
            sha256=hashlib.sha256(jpeg).hexdigest(),
            width=width,
            height=height,
            faces=faces,
        )
