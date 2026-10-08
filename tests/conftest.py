import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from porchlight.app import create_app
from porchlight.config import Config

ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(data_root=tmp_path / "profile")


@pytest.fixture
def client(config: Config) -> Iterator[TestClient]:
    with TestClient(create_app(config), base_url=ORIGIN, client=("127.0.0.1", 42000)) as client:
        yield client


def claim(client: TestClient) -> str:
    token = client.get(
        "/api/v1/setup/bootstrap", headers={"X-Porchlight-Bootstrap": "local-setup"}
    ).json()["token"]
    response = client.post(
        "/api/v1/setup/claim",
        headers={"Origin": ORIGIN},
        json={
            "login_name": "synthetic_owner",
            "password": "synthetic-test-passphrase",
            "bootstrap_token": token,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["csrf_token"])


@pytest.fixture
def authenticated(client: TestClient) -> tuple[TestClient, dict[str, str]]:
    csrf = claim(client)
    return client, {"Origin": ORIGIN, "X-CSRF-Token": csrf}


@pytest.fixture
def synthetic_mp4(config: Config, tmp_path: Path) -> bytes:
    executable = config.tool_path("ffmpeg")
    if executable is None:
        pytest.skip("FFmpeg unavailable; install explicitly to run decoder tests")
    path = tmp_path / "synthetic.mp4"
    subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "color=c=orange:s=320x240:d=1",
            "-c:v",
            "mpeg4",
            "-y",
            str(path),
        ],
        check=True,
        timeout=30,
    )
    return path.read_bytes()


@pytest.fixture
def synthetic_jpeg(config: Config, tmp_path: Path) -> bytes:
    executable = config.tool_path("ffmpeg")
    if executable is None:
        pytest.skip("FFmpeg unavailable; install explicitly to run decoder tests")
    path = tmp_path / "synthetic.jpg"
    subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240",
            "-frames:v",
            "1",
            "-c:v",
            "mjpeg",
            "-y",
            str(path),
        ],
        check=True,
        timeout=30,
    )
    return path.read_bytes()
