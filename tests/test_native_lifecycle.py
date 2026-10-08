import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx


def test_native_launch_identity_and_cooperative_stop_with_open_stream(tmp_path: Path) -> None:
    """Exercise the actual server, profile lock and streaming shutdown on an empty profile."""
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    profile = tmp_path / "synthetic-profile"
    instance = str(uuid4())
    environment = dict(os.environ)
    environment.pop("PORCHLIGHT_PUBLIC_ORIGIN", None)
    environment.update(
        PORCHLIGHT_DATA_ROOT=str(profile),
        PORCHLIGHT_PORT=str(port),
        PORCHLIGHT_DEV_FRONTEND="false",
    )
    origin = f"http://127.0.0.1:{port}"
    marker = profile / "process.json"
    stop = profile / f"{instance}.stop"
    with (tmp_path / "synthetic-server.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "porchlight", "--launch-id", instance],
            env=environment,
            stdout=log,
            stderr=log,
        )
        try:
            with httpx.Client(base_url=origin, timeout=5, trust_env=False) as client:
                deadline = time.monotonic() + 20
                while True:
                    assert process.poll() is None, "Synthetic server exited during startup"
                    try:
                        if marker.exists() and client.get("/health/live").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic() < deadline, "Synthetic server was not ready"
                    time.sleep(0.1)
                metadata = json.loads(marker.read_text(encoding="utf-8"))
                assert metadata["instance"] == instance and metadata["port"] == port
                token = client.get(
                    "/api/v1/setup/bootstrap",
                    headers={"X-Porchlight-Bootstrap": "local-setup"},
                ).json()["token"]
                result = client.post(
                    "/api/v1/setup/claim",
                    headers={"Origin": origin},
                    json={
                        "login_name": "synthetic_owner",
                        "password": "synthetic-test-passphrase",
                        "bootstrap_token": token,
                    },
                )
                assert result.status_code == 201
                with client.stream("GET", "/api/v1/stream") as stream:
                    assert stream.status_code == 200
                    lines = stream.iter_lines()
                    assert next(lines) == "retry: 5000"
                    assert next(lines) == ""
                    # Read through initial resync; its epoch is independent of launch identity.
                    for line in lines:
                        if line == "event: resync":
                            break
                    else:
                        raise AssertionError("Missing initial stream resync")
                    stop.touch()
                    process.wait(timeout=20)
                    assert process.returncode == 0
                    list(lines)  # A connected SSE client must not keep shutdown alive.
                assert not marker.exists() and not stop.exists()
        finally:
            if process.poll() is None:
                profile.mkdir(parents=True, exist_ok=True)
                stop.touch()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate()  # Only this test's directly owned synthetic process.
                    process.wait(timeout=10)
