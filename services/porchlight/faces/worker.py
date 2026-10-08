"""Bounded subprocess with no network or tools; input contains decoded local JPEGs only."""

import base64
import json
import sys
from pathlib import Path

from porchlight.faces.contracts import FaceReport
from porchlight.faces.detector import Detector
from porchlight.faces.recognizer import MANIFEST as RECOGNIZER_MANIFEST


def main() -> None:
    payload = sys.stdin.buffer.read(24 * 1024**2 + 1)
    if len(payload) > 24 * 1024**2:
        raise ValueError("Input budget exceeded")
    request = json.loads(payload)
    frames = request["frames"]
    if not 1 <= len(frames) <= 48:
        raise ValueError("Frame budget exceeded")
    profiles = request.get("profiles", {})
    if not isinstance(profiles, dict) or len(profiles) > 100:
        raise ValueError("Profile budget exceeded")
    if any(
        not isinstance(examples, list) or not 1 <= len(examples) <= 32
        for examples in profiles.values()
    ):
        raise ValueError("Sample budget exceeded")
    model = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    detector = Detector(Path(sys.argv[1]), model, profiles)
    report = FaceReport(
        recognition_model_sha256=RECOGNIZER_MANIFEST["sha256"] if profiles else None,
        frames=[
            detector.detect(base64.b64decode(f["jpeg"], validate=True), int(f["offset_ms"]))
            for f in frames
        ],
    )
    sys.stdout.write(report.model_dump_json())


if __name__ == "__main__":
    main()
