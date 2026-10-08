"""Explicit installer only: bounded download, pinned digest, atomic local promotion."""

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="C:/local-models/yunet-face-detection")
    options = parser.parse_args()
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "services/porchlight/face_model.json").read_text()
    )
    folder = Path(options.directory).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / manifest["filename"]
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == manifest["sha256"]:
        print("Pinned detector already present.")
    else:
        if path.exists():
            raise ValueError("Existing model differs; preserve it and resolve the mismatch first.")
        with urllib.request.urlopen(manifest["url"], timeout=30) as response:
            content = response.read(manifest["bytes"] + 1)
        if (
            len(content) != manifest["bytes"]
            or hashlib.sha256(content).hexdigest() != manifest["sha256"]
        ):
            raise ValueError("Detector bytes do not match the pinned upstream model.")
        temporary = path.with_suffix(".partial")
        temporary.write_bytes(content)
        os.replace(temporary, path)
        print("Pinned local detector installed. Automatic detection remains off.")
    # Repair a missing notice even when a previous model download already succeeded.
    if not (folder / "LICENSE").is_file():
        with urllib.request.urlopen(manifest["license_url"], timeout=15) as response:
            license_text = response.read(16385)
        if len(license_text) > 16384 or not license_text.startswith(b"MIT License"):
            raise ValueError("Review the model license before completing installation.")
        (folder / "LICENSE").write_bytes(license_text)
