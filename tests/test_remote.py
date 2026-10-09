import pytest
from conftest import ORIGIN, claim
from fastapi.testclient import TestClient
from porchlight.app import create_app
from porchlight.config import Config

PUBLIC = "https://porchlight.example.test"
LOGIN = {"login_name": "synthetic_owner", "password": "synthetic-test-passphrase"}


def test_home_screen_navigation_can_load_only_public_shell(config, tmp_path) -> None:
    config.web_dist = tmp_path / "web"
    config.web_dist.mkdir()
    (config.web_dist / "index.html").write_text("<!doctype html><title>Porchlight</title>")
    with TestClient(create_app(config), base_url=ORIGIN, client=("127.0.0.1", 40000)) as local:
        claim(local)
    config.public_origin = PUBLIC
    launch = {
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
    }
    with TestClient(create_app(config), base_url=PUBLIC, client=("127.0.0.1", 40000)) as remote:
        for origin in [
            None,
            "null",
            "android-app://org.chromium.webapk.synthetic",
            "https://external.example",
        ]:
            headers = {**launch, **({"Origin": origin} if origin is not None else {})}
            for path in ["/", "/index.html"]:
                response = remote.get(path, headers=headers)
                assert response.status_code == 200, response.text
                assert "text/html" in response.headers["content-type"]
                assert response.headers["X-Frame-Options"] == "DENY"
            for path in [
                "/api/v1/auth/session",
                "/api/v1/events",
                "/api/v1/media/synthetic",
                "/health/live",
                "/sw.js",
            ]:
                assert remote.get(path, headers=headers).status_code == 403
            assert remote.post("/api/v1/auth/login", headers=headers, json=LOGIN).status_code == 403
        for changes in [
            {"Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"},
            {"Sec-Fetch-Mode": "same-origin", "Sec-Fetch-Dest": "empty"},
            {"Sec-Fetch-Dest": "empty"},
            {"Sec-Fetch-Mode": "", "Sec-Fetch-Dest": ""},
        ]:
            headers = {**launch, **changes, "Origin": "null"}
            for path in ["/", "/index.html?launch=synthetic"]:
                response = remote.get(path, headers=headers)
                assert response.status_code == 200, response.text
                assert response.headers["X-Frame-Options"] == "DENY"
                assert "access-control-allow-origin" not in response.headers
            for path in ["/api/v1/auth/session", "/api/v1/events", "/api/v1/media/synthetic"]:
                response = remote.get(path, headers=headers)
                assert response.status_code == 403
                assert response.headers["Cache-Control"] == "no-store"
            assert remote.post("/", headers=headers).status_code == 403
        for changes in [
            {"Sec-Fetch-Dest": "iframe"},
            {"Sec-Fetch-Dest": "object"},
            {"Sec-Fetch-Dest": "embed"},
        ]:
            assert remote.get("/", headers={**launch, **changes}).status_code == 403
        assert remote.get("/", headers={**launch, "Host": "unapproved.example"}).status_code == 400
        login = remote.post("/api/v1/auth/login", headers={"Origin": PUBLIC}, json=LOGIN)
        assert login.status_code == 200
        assert (
            remote.get(
                "/api/v1/auth/session", headers={"Sec-Fetch-Site": "same-origin"}
            ).status_code
            == 200
        )
        assert remote.get("/api/v1/auth/session", headers=launch).status_code == 403
        assert remote.post("/api/v1/auth/logout", headers={"Origin": PUBLIC}).status_code == 403


@pytest.mark.parametrize(
    "origin",
    [
        "http://porch.example",
        "https://*.example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://127.0.0.1",
        "https://example.com:8765",
    ],
)
def test_remote_origin_requires_one_explicit_https_domain(origin, tmp_path) -> None:
    with pytest.raises(ValueError):
        Config(data_root=tmp_path, public_origin=origin)


def test_remote_mode_requires_local_setup(config) -> None:
    config.public_origin = PUBLIC
    with pytest.raises(RuntimeError, match="loopback owner setup"):
        with TestClient(create_app(config), base_url=PUBLIC):
            pass


def test_exact_loopback_proxy_https_secure_sessions_csrf_and_media(config, synthetic_mp4) -> None:
    with TestClient(create_app(config), base_url=ORIGIN, client=("127.0.0.1", 40000)) as local:
        token = claim(local)
        media = local.post(
            "/api/v1/imports",
            headers={"Origin": ORIGIN, "X-CSRF-Token": token, "Content-Type": "video/mp4"},
            content=synthetic_mp4,
        ).json()
    config.public_origin = PUBLIC
    with TestClient(create_app(config), base_url=PUBLIC, client=("127.0.0.1", 40000)) as remote:
        assert (
            remote.get(
                "/api/v1/setup/bootstrap", headers={"X-Porchlight-Bootstrap": "local-setup"}
            ).status_code
            == 403
        )
        assert remote.get(f"/api/v1/media/{media['media_id']}").status_code == 401
        login = remote.post("/api/v1/auth/login", headers={"Origin": PUBLIC}, json=LOGIN)
        assert login.status_code == 200
        assert "Secure" in login.headers["set-cookie"] and "HttpOnly" in login.headers["set-cookie"]
        assert login.headers["Strict-Transport-Security"] == "max-age=31536000"
        assert (
            remote.get(
                f"/api/v1/media/{media['media_id']}", headers={"Range": "bytes=0-3"}
            ).status_code
            == 206
        )
        assert (
            remote.patch(
                f"/api/v1/events/{media['id']}/annotation",
                headers={"Origin": PUBLIC},
                json={"note": "unsafe", "favourite": False},
            ).status_code
            == 403
        )
        assert remote.get("/health/live", headers={"Origin": ORIGIN}).status_code == 403
        assert (
            remote.get("/health/live", headers={"Host": "unapproved.example.test"}).status_code
            == 400
        )
    # Uvicorn remains loopback-only with proxy_headers=False. No forwarded client/host is trusted.
    with TestClient(
        create_app(config), base_url="http://porchlight.example.test", client=("127.0.0.1", 40000)
    ) as proxy:
        assert proxy.get("/health/live").status_code == 403
        assert proxy.get("/health/live", headers={"X-Forwarded-Proto": "https"}).status_code == 200
        assert (
            proxy.get("/health/live", headers={"X-Forwarded-Proto": "https,http"}).status_code
            == 403
        )
    with TestClient(create_app(config), base_url=PUBLIC, client=("192.0.2.15", 40000)) as direct:
        assert direct.get("/health/live", headers={"X-Forwarded-Proto": "https"}).status_code == 403


def test_push_pairing_requires_remote_https_owner_session_and_csrf(config) -> None:
    from porchlight.push import WebPush
    from test_push import Sender, Vault, pairing

    vault = Vault()
    with TestClient(create_app(config), base_url=ORIGIN, client=("127.0.0.1", 40000)) as local:
        token = claim(local)
        config.public_origin = PUBLIC
        push = WebPush(config, local.app.state.db, vault, Sender())
        local.app.state.push = push
        setup = local.post(
            "/api/v1/push/configure", headers={"Origin": ORIGIN, "X-CSRF-Token": token}
        )
        assert setup.status_code == 200 and setup.json()["configured"]
        assert (
            local.post(
                "/api/v1/push/devices",
                headers={"Origin": ORIGIN, "X-CSRF-Token": token},
                json=pairing().model_dump(),
            ).status_code
            == 409
        )
    with TestClient(create_app(config), base_url=PUBLIC, client=("127.0.0.1", 40000)) as remote:
        remote.app.state.push = WebPush(config, remote.app.state.db, vault, Sender())
        body = pairing().model_dump()
        assert (
            remote.post("/api/v1/push/devices", headers={"Origin": PUBLIC}, json=body).status_code
            == 401
        )
        response = remote.post("/api/v1/auth/login", headers={"Origin": PUBLIC}, json=LOGIN)
        assert response.status_code == 200
        headers = {"Origin": PUBLIC, "X-CSRF-Token": response.json()["csrf_token"]}
        assert (
            remote.post("/api/v1/push/devices", headers={"Origin": PUBLIC}, json=body).status_code
            == 403
        )
        assert remote.post("/api/v1/push/configure", headers=headers).status_code == 403
        paired = remote.post("/api/v1/push/devices", headers=headers, json=body)
        assert paired.status_code == 201, paired.text
        identifier = paired.json()["paired_device_id"]
        assert body["endpoint"] not in paired.text and body["keys"]["auth"] not in paired.text
        assert (
            remote.post(f"/api/v1/push/devices/{identifier}/test", headers=headers).status_code
            == 202
        )
        assert (
            remote.delete(f"/api/v1/push/devices/{identifier}", headers=headers).status_code == 204
        )
