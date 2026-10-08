"""Explicit, digest-verified local installer for OpenCV Zoo SFace."""

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path


def download(url: str, limit: int, timeout: int) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Upstream file exceeds the pinned size limit.")
    return content


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="C:/local-models/sface-recognition")
    options = parser.parse_args()
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "services/porchlight/sface_model.json").read_text(
            encoding="utf-8"
        )
    )
    folder = Path(options.directory).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    model = folder / manifest["filename"]
    expected_bytes = int(manifest["bytes"])

    if model.exists():
        if (
            model.stat().st_size != expected_bytes
            or hashlib.sha256(model.read_bytes()).hexdigest() != manifest["sha256"]
        ):
            raise ValueError(
                "Existing SFace model differs; preserve it and resolve the mismatch first."
            )
        print("Pinned SFace model already present.")
    else:
        content = download(manifest["url"], expected_bytes, 60)
        if (
            len(content) != expected_bytes
            or hashlib.sha256(content).hexdigest() != manifest["sha256"]
        ):
            raise ValueError("Downloaded SFace model does not match its pinned size and SHA-256.")
        partial = model.with_suffix(".partial")
        try:
            partial.write_bytes(content)
            os.replace(partial, model)
        finally:
            partial.unlink(missing_ok=True)
        print("Pinned SFace model installed.")

    license_path = folder / "LICENSE"
    if license_path.is_file():
        license_text = license_path.read_bytes()
    else:
        license_text = download(manifest["license_url"], manifest["license_bytes"], 15)
    if (
        len(license_text) != manifest["license_bytes"]
        or hashlib.sha256(license_text).hexdigest() != manifest["license_sha256"]
    ):
        raise ValueError("SFace license differs from the pinned upstream file.")
    if not license_path.is_file():
        license_path.write_bytes(license_text)
    print("SFace model and license verified locally. Recognition remains off until configured.")


if __name__ == "__main__":
    main()
