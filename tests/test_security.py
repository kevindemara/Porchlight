import concurrent.futures
import time
from pathlib import Path

import pytest
from conftest import ORIGIN, claim
from fastapi.testclient import TestClient
from porchlight import config as configuration
from porchlight.app import create_app
from porchlight.config import ROOT, Config
from porchlight.security.auth import COOKIE
from porchlight.storage.models import Owner, Session
from sqlalchemy import select


def test_mapped_network_volume_is_rejected_before_creating_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "new-profile"
    monkeypatch.setattr(configuration, "is_remote_volume", lambda _: True)
    with pytest.raises(ValueError, match="mapped network drive"):
        Config(data_root=destination)
    assert not destination.exists()


def test_native_local_volume_is_accepted_without_filesystem_mutation(tmp_path: Path) -> None:
    destination = tmp_path / "new-profile"
    assert not configuration.is_remote_volume(destination)
    assert Config(data_root=destination).data_root == destination.resolve()
    assert not destination.exists()


def test_unclaimed_has_no_fake_data(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/api/v1/setup/state").json() == {"owner_created": False}
    for path in ["health", "settings", "cameras", "events", "ollama/models", "openapi.json"]:
        assert client.get(f"/api/v1/{path}").status_code == 401


def test_host_origin_and_missing_origin_are_rejected(client: TestClient) -> None:
    assert client.get("/health/live", headers={"Host": "evil.test:8765"}).status_code == 400
    assert client.get("/health/live", headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.get("/health/live", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/v1/auth/login", json={}).status_code == 403
    assert client.get("/api/v1/setup/bootstrap").status_code == 403


@pytest.mark.parametrize("dev_frontend", [False, True])
def test_development_origin_is_scoped_to_the_selected_port(
    config: Config, dev_frontend: bool
) -> None:
    config.dev_frontend = dev_frontend
    with TestClient(create_app(config), base_url=ORIGIN) as client:
        assert client.get(
            "/health/live", headers={"Origin": "http://127.0.0.1:5174"}
        ).status_code == (200 if dev_frontend else 403)
        assert (
            client.get("/health/live", headers={"Origin": "http://127.0.0.1:5173"}).status_code
            == 403
        )


def test_bootstrap_is_one_use_and_password_is_hashed(client: TestClient) -> None:
    claim(client)
    assert (
        client.get(
            "/api/v1/setup/bootstrap", headers={"X-Porchlight-Bootstrap": "local-setup"}
        ).status_code
        == 409
    )
    with client.app.state.db.session() as db:
        owner = db.get(Owner, "owner")
        assert owner.password_hash.startswith("$argon2id$")
        session = db.scalar(select(Session))
        assert client.cookies[COOKIE] != session.id_hash
    cookie = client.cookies[COOKIE]
    response = client.get("/api/v1/auth/session")
    assert cookie not in response.text
    assert "synthetic-test-passphrase" not in response.text


def test_expired_bootstrap_and_remote_setup_fail(client: TestClient, config: Config) -> None:
    client.app.state.auth.bootstrap_expiry = time.time() - 1
    assert (
        client.get(
            "/api/v1/setup/bootstrap", headers={"X-Porchlight-Bootstrap": "local-setup"}
        ).status_code
        == 409
    )
    # A new app on a different profile emulates a remote client without touching a camera.
    config = config.model_copy(update={"data_root": config.data_root.parent / "remote"})
    with TestClient(create_app(config), base_url=ORIGIN, client=("192.0.2.1", 1)) as remote:
        assert (
            remote.get(
                "/api/v1/setup/bootstrap", headers={"X-Porchlight-Bootstrap": "local-setup"}
            ).status_code
            == 403
        )


def test_claim_race_creates_one_owner(client: TestClient) -> None:
    token = client.get(
        "/api/v1/setup/bootstrap", headers={"X-Porchlight-Bootstrap": "local-setup"}
    ).json()["token"]

    def attempt(index: int) -> int:
        return client.post(
            "/api/v1/setup/claim",
            headers={"Origin": ORIGIN},
            json={
                "login_name": f"owner_{index}",
                "password": "synthetic-test-passphrase",
                "bootstrap_token": token,
            },
        ).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(attempt, range(2))) == [201, 409]


def test_logout_revokes_and_csrf_is_required(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    old_cookie = client.cookies[COOKIE]
    assert client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    client.cookies.set(COOKIE, old_cookie)
    assert client.get("/api/v1/auth/session").status_code == 401


def test_session_expiry_and_rotation(authenticated: tuple[TestClient, dict[str, str]]) -> None:
    client, _ = authenticated
    old_cookie = client.cookies[COOKIE]
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={
            "login_name": "synthetic_owner",
            "password": "synthetic-test-passphrase",
        },
    )
    assert response.status_code == 200
    assert client.cookies[COOKIE] != old_cookie
    with client.app.state.db.session() as db:
        sessions = list(db.scalars(select(Session)))
        assert len(sessions) == 1
        sessions[0].expires_at = time.time() - 1
        db.commit()
    assert client.get("/api/v1/auth/session").status_code == 401


def test_bad_login_is_throttled_and_errors_never_echo_secrets(client: TestClient) -> None:
    claim(client)
    private_value = "DO-NOT-ECHO-THIS-SECRET"
    for _ in range(8):
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={
                "login_name": "unknown",
                "password": private_value,
            },
        )
        assert response.status_code == 401
        assert private_value not in response.text
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={
            "login_name": "unknown",
            "password": private_value,
        },
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    invalid = client.post(
        "/api/v1/setup/claim", headers={"Origin": ORIGIN}, json={"password": private_value}
    )
    assert invalid.status_code == 422
    assert private_value not in invalid.text


def test_single_instance_lock(client: TestClient, config: Config) -> None:
    with pytest.raises(RuntimeError, match="already running"):
        with TestClient(create_app(config), base_url=ORIGIN):
            pass


def test_runtime_and_cloud_endpoints_rejected(tmp_path: Path) -> None:
    for address in [
        "http://example.com:11434",
        "http://127.0.0.1:8765",
        "http://localhost:11434/a",
        "http://user:pass@localhost:11434",
    ]:
        with pytest.raises(ValueError):
            Config(data_root=tmp_path, ollama_url=address)
    with pytest.raises(ValueError):
        Config(host="0.0.0.0", data_root=tmp_path)
    with pytest.raises(ValueError):
        Config(data_root=ROOT / "runtime")
    with pytest.raises(ValueError):
        Config(data_root=tmp_path, timezone="not-a-timezone")


def test_large_and_chunked_json_are_bounded(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/auth/login", headers={"Origin": ORIGIN}, content=b"x" * 20000
        ).status_code
        == 413
    )

    def stream():
        yield b"x" * 10000
        yield b"x" * 10000

    assert (
        client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, content=stream()).status_code
        == 413
    )
