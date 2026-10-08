"""Validate a startup configuration without creating profiles or Windows tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from porchlight.config import ROOT, Config


def plan(config: Config) -> dict[str, object]:
    identifier = hashlib.sha256(
        (str(ROOT).casefold() + "\n" + str(config.data_root).casefold()).encode()
    ).hexdigest()[:16]
    paths = [ROOT, config.data_root]
    if config.data_root == Path(config.data_root.anchor):
        raise ValueError("Use a dedicated profile folder, not a drive root.")
    if any(any(character in str(path) for character in ('"', "\r", "\n", "\0")) for path in paths):
        raise ValueError("Startup paths contain unsupported characters.")
    return {
        "task_name": "Porchlight-" + identifier,
        "description": "Porchlight startup v1 " + identifier,
        "repository": str(ROOT),
        "launcher": str(ROOT / "scripts/run-startup.ps1"),
        "data_root": str(config.data_root),
        "port": config.port,
        "public_origin": config.public_origin,
        "ffmpeg": config.tool_path("ffmpeg"),
        "ffprobe": config.tool_path("ffprobe"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--public-origin")
    args = parser.parse_args()
    values = {name: value for name, value in vars(args).items() if value is not None}
    try:
        print(json.dumps(plan(Config(**values))))
        return 0
    except Exception:
        print(json.dumps({"error": "Review the local data path, port and exact HTTPS origin."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
