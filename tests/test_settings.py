from conftest import ORIGIN, claim
from fastapi.testclient import TestClient
from porchlight.app import create_app
from porchlight.config import Config
from porchlight.storage.models import SettingsRow


def test_settings_conflicts_and_private_ai_gate(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    settings = client.get("/api/v1/settings").json()
    assert settings["ai_enabled"] is False
    assert settings["retention_enabled"] is False
    response = client.put("/api/v1/settings", headers=headers, json={**settings, "theme": "dark"})
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert client.put("/api/v1/settings", headers=headers, json=settings).status_code == 409
    current = response.json()
    assert (
        client.put(
            "/api/v1/settings", headers=headers, json={**current, "ai_enabled": True}
        ).status_code
        == 409
    )
    assert (
        client.put(
            "/api/v1/settings", headers=headers, json={**current, "retention_enabled": True}
        ).status_code
        == 409
    )
    assert (
        client.put(
            "/api/v1/settings", headers=headers, json={**current, "timezone": "invalid"}
        ).status_code
        == 422
    )


def test_health_reports_independent_unverified_components(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = authenticated
    status = client.get("/api/v1/health").json()
    assert status["database"]["state"] == "ready"
    assert status["blink"]["state"] == "not_configured"
    assert status["ai"]["state"] == "unverified"
    assert status["live_view"]["state"] in {"unverified", "unavailable"}
    assert "Experimental" in status["live_view"]["message"]
    assert status["camera_count"] == 0
    assert client.get("/api/v1/cameras").json() == {"items": []}


def test_hardware_guidance_persists_without_granting_storage_capability(config: Config) -> None:
    with TestClient(create_app(config), base_url=ORIGIN, client=("127.0.0.1", 42000)) as client:
        csrf = claim(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        initial = client.get("/api/v1/settings").json()
        assert initial["blink_camera_setup"] == initial["blink_module_setup"] == "unknown"
        response = client.put(
            "/api/v1/settings",
            headers=headers,
            json={**initial, "blink_camera_setup": "mixed", "blink_module_setup": "xr_plus"},
        )
        assert response.status_code == 200
        for key in ("ai_enabled", "retention_enabled", "blink_entitlement"):
            assert response.json()[key] == initial[key]
        assert not client.get("/api/v1/integrations/blink/local-recordings").json()["eligible"]
        denied = client.post(
            "/api/v1/integrations/blink/local-sync", headers=headers, json={"enabled": True}
        )
        assert denied.status_code == 409 and denied.json()["code"] == "LOCAL_STORAGE_NOT_READY"
        assert not client.get("/api/v1/integrations/blink/recordings").json()["no_plan_verified"]
        assert client.put("/api/v1/settings", headers=headers, json=initial).status_code == 409
        current = response.json()
        for changes in ({"blink_module_setup": "invented"}, {"blink_camera_setup": "invented"}):
            assert (
                client.put(
                    "/api/v1/settings", headers=headers, json={**current, **changes}
                ).status_code
                == 422
            )
        assert client.put("/api/v1/settings", json=current).status_code == 403
    with TestClient(create_app(config), base_url=ORIGIN, client=("127.0.0.1", 42000)) as restarted:
        assert (
            restarted.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN},
                json={"login_name": "synthetic_owner", "password": "synthetic-test-passphrase"},
            ).status_code
            == 200
        )
        saved = restarted.get("/api/v1/settings").json()
        assert saved["blink_module_setup"] == "xr_plus" and saved["blink_camera_setup"] == "mixed"
        local = restarted.get("/api/v1/integrations/blink/local-recordings").json()
        assert not local["eligible"] and not local["sync"]["enabled"]


def test_older_profile_keeps_safe_unknown_hardware_defaults(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = authenticated
    with client.app.state.db.session() as db:
        row = db.get(SettingsRow, 1)
        assert row is not None
        previous = dict(row.values)
        previous.pop("blink_module_setup", None)
        previous.pop("blink_camera_setup", None)
        row.values = previous
        db.commit()
    current = client.get("/api/v1/settings").json()
    assert current["blink_module_setup"] == current["blink_camera_setup"] == "unknown"
    assert current["blink_entitlement"] == previous["blink_entitlement"]
    assert current["ai_enabled"] == previous["ai_enabled"]
