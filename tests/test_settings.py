from fastapi.testclient import TestClient


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
