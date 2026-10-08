"""CPU-only SFace embeddings. Vectors stay local and never enter public reports."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from porchlight.api.contracts import ApiError
from porchlight.faces.contracts import FaceBox
from porchlight.faces.detector import DETECTOR_THRESHOLD, check_runtime

MANIFEST = json.loads((Path(__file__).parents[1] / "sface_model.json").read_text())
DIMENSIONS = 128
MATCH_THRESHOLD = 0.45
MATCH_MARGIN = 0.08


def check_recognizer(path: Path) -> None:
    if not path.is_file() or path.stat().st_size != MANIFEST["bytes"]:
        raise ApiError(409, "SFACE_MODEL_REQUIRED", "Install the verified local SFace model.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != MANIFEST["sha256"]:
        raise ApiError(409, "SFACE_MODEL_MISMATCH", "The SFace model has a different digest.")


def normalized(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) != DIMENSIONS:
        raise ValueError("Invalid SFace vector dimensions")
    vector = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("Invalid SFace vector values")
    length = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(length) or length < 1e-8:
        raise ValueError("Empty SFace vector")
    return tuple(value / length for value in vector)


def cosine_score(first: Sequence[float], second: Sequence[float]) -> float:
    left, right = normalized(first), normalized(second)
    return sum(a * b for a, b in zip(left, right, strict=True))


def best_match(
    feature: Sequence[float], profiles: Mapping[str, Sequence[Sequence[float]]]
) -> tuple[str, float] | None:
    scores = rank_profiles(feature, profiles)
    if not scores or scores[0][1] < MATCH_THRESHOLD:
        return None
    if len(scores) > 1 and scores[0][1] - scores[1][1] < MATCH_MARGIN:
        return None
    return scores[0]


def rank_profiles(
    feature: Sequence[float], profiles: Mapping[str, Sequence[Sequence[float]]]
) -> list[tuple[str, float]]:
    return sorted(
        (
            (identifier, max(cosine_score(feature, vector) for vector in examples))
            for identifier, examples in profiles.items()
            if examples
        ),
        key=lambda item: item[1],
        reverse=True,
    )


class Recognizer:
    def __init__(self, path: Path):
        check_recognizer(path)
        self.cv: Any = importlib.import_module("cv2")
        self.native = self.cv.FaceRecognizerSF.create(str(path), "")

    def extract(self, image: Any, yunet_row: Any) -> tuple[float, ...]:
        aligned = self.native.alignCrop(image, yunet_row)
        feature = self.native.feature(aligned)
        return normalized(feature.reshape(-1).tolist())


def feature_for_box(
    jpeg: bytes, detector_path: Path, recognizer_path: Path, target: FaceBox,
    recognizer: Recognizer | None = None,
) -> tuple[float, ...]:
    """Re-detect a verified sample and select its matching YuNet landmark row."""
    check_runtime(detector_path)
    cv: Any = importlib.import_module("cv2")
    np: Any = importlib.import_module("numpy")
    image = cv.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid evidence image")
    height, width = image.shape[:2]
    if not 0 < width <= 960 or not 0 < height <= 960:
        raise ValueError("Image budget exceeded")
    detector = cv.FaceDetectorYN.create(
        str(detector_path), "", (width, height), DETECTOR_THRESHOLD, 0.3, 5000
    )
    _, rows = detector.detect(image)
    if rows is None or len(rows) > 25:
        raise ValueError("Selected face is unavailable")

    def overlap(row: Any) -> float:
        x, y, w, h = (float(row[i]) for i in range(4))
        if not all(math.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0:
            return 0.0
        x2, y2 = max(x, target.x), max(y, target.y)
        right = min(x + w, target.x + target.width)
        bottom = min(y + h, target.y + target.height)
        intersection = max(0.0, right - x2) * max(0.0, bottom - y2)
        union = w * h + target.width * target.height - intersection
        return intersection / union if union > 0 else 0.0

    row = max(rows, key=overlap)
    if overlap(row) < 0.7:
        raise ValueError("Selected face no longer matches the sampled recording")
    return (recognizer or Recognizer(recognizer_path)).extract(image, row)
