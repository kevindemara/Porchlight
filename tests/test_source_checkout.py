"""Copied source/resources, existing dependencies and synthetic data: no fresh install claim."""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from porchlight.config import ROOT


def test_copied_source_runs_and_restarts_with_existing_runtime(
    tmp_path: Path, synthetic_mp4: bytes
) -> None:
    checkout = tmp_path / "copied checkout with [literal] spaces"
    for relative in ("services/porchlight", "schemas", "prompts", "apps/web/dist"):
        shutil.copytree(
            ROOT / relative,
            checkout / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    profile = tmp_path / "isolated-synthetic-profile"
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("PORCHLIGHT_")
    }
    environment.update(
        PYTHONPATH=str(checkout / "services"),
        PYTHONDONTWRITEBYTECODE="1",
        PORCHLIGHT_DATA_ROOT=str(profile),
        PORCHLIGHT_PORT=str(port),
    )
    bootstrap = (
        "from pathlib import Path; import porchlight, runpy; "
        "from porchlight.config import ROOT; "
        "assert Path(porchlight.__file__).resolve().is_relative_to(Path.cwd() / 'services'); "
        "assert ROOT == Path.cwd(); runpy.run_module('porchlight', run_name='__main__')"
    )
    event_id, media_id = "", ""
    for iteration in range(2):
        instance = str(uuid4())
        stop = profile / f"{instance}.stop"
        with (tmp_path / f"synthetic-snapshot-{iteration}.log").open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, "-c", bootstrap, "--launch-id", instance],
                cwd=checkout,
                env=environment,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                with httpx.Client(base_url=origin, timeout=5, trust_env=False) as client:
                    deadline = time.monotonic() + 20
                    while True:
                        assert process.poll() is None, "Copied-source server exited during startup"
                        try:
                            if (profile / "process.json").exists() and client.get(
                                "/health/live"
                            ).status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        assert time.monotonic() < deadline, "Copied-source server was not ready"
                        time.sleep(0.1)
                    metadata = json.loads((profile / "process.json").read_text(encoding="utf-8"))
                    assert metadata["instance"] == instance and metadata["port"] == port
                    shell = client.get("/")
                    assert shell.status_code == 200 and '<div id="root">' in shell.text
                    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', shell.text)
                    assert len(assets) >= 2
                    for asset in assets:
                        assert client.get(asset).status_code == 200
                    assert client.get("/api/v1/events").status_code == 401
                    assert client.get("/api/v1/settings").status_code == 401
                    if iteration == 0:
                        token = client.get(
                            "/api/v1/setup/bootstrap",
                            headers={"X-Porchlight-Bootstrap": "local-setup"},
                        ).json()["token"]
                        login = client.post(
                            "/api/v1/setup/claim",
                            headers={"Origin": origin},
                            json={
                                "login_name": "synthetic_owner",
                                "password": "synthetic-test-passphrase",
                                "bootstrap_token": token,
                            },
                        )
                    else:
                        login = client.post(
                            "/api/v1/auth/login",
                            headers={"Origin": origin},
                            json={
                                "login_name": "synthetic_owner",
                                "password": "synthetic-test-passphrase",
                            },
                        )
                    assert login.status_code == (201 if iteration == 0 else 200)
                    headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}
                    if iteration == 0:
                        imported = client.post(
                            "/api/v1/imports",
                            headers={**headers, "Content-Type": "video/mp4"},
                            content=synthetic_mp4,
                        )
                        assert imported.status_code == 201
                        event = imported.json()
                        event_id, media_id = event["id"], event["media_id"]
                    events = client.get("/api/v1/events").json()["items"]
                    assert len(events) == 1 and events[0]["id"] == event_id
                    assert events[0]["source_type"] == "manual_import"
                    assert events[0]["analysis_status"] == "not_analyzed"
                    media = f"/api/v1/media/{media_id}"
                    assert client.get(media).content == synthetic_mp4
                    partial = client.get(media, headers={"Range": "bytes=0-15"})
                    assert partial.status_code == 206 and partial.content == synthetic_mp4[:16]
                    assert partial.headers["cache-control"] == "no-store"
                    assert client.head(media).status_code == 200
                    assert client.get(media + "/thumbnail").status_code == 200
                    assert client.get("/api/v1/settings").json()["ai_enabled"] is False
                    client.cookies.clear()
                    assert client.get(media).status_code == 401
                    assert client.head(media, headers={"Range": "bytes=0-15"}).status_code == 401
                    stop.touch()
                    process.wait(timeout=20)
                    assert process.returncode == 0
                    assert not (profile / "process.json").exists() and not stop.exists()
            finally:
                if process.poll() is None:
                    profile.mkdir(parents=True, exist_ok=True)
                    stop.touch()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.terminate()  # Only the directly owned synthetic child process.
                        process.wait(timeout=10)
    assert not (checkout / "media").exists() and not (checkout / "porchlight.db").exists()
    assert (checkout / "prompts/VISION_SYSTEM.md").read_bytes() == (
        ROOT / "prompts/VISION_SYSTEM.md"
    ).read_bytes()
