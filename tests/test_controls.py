import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError, CameraCommandRequest, CameraView
from porchlight.controls import CameraControls
from porchlight.storage.database import Database
from porchlight.storage.models import CameraCommand


class Provider:
    def __init__(self) -> None:
        self.cameras = [
            CameraView(
                id=str(uuid4()),
                name="Synthetic camera",
                family="cameras",
                network_name="Synthetic network",
                observed_armed=True,
                observed_motion=True,
                network_control=True,
                motion_control=True,
            )
        ]
        self.calls: list[tuple[str, bool]] = []
        self.verifications = 0
        self.result: bool | None = None
        self.wait: asyncio.Event | None = None

    async def set_camera_state(
        self, camera_id: str, operation: str, desired: bool, is_authorized=None
    ) -> bool | None:
        self.calls.append((operation, desired))
        if self.wait:
            await self.wait.wait()
        return self.result

    async def verify_camera_state(self, camera_id: str, operation: str) -> bool | None:
        self.verifications += 1
        return self.result


def request(desired: bool = True, **values) -> CameraCommandRequest:
    return CameraCommandRequest(
        request_id=str(uuid4()), operation="network_armed", desired=desired, **values
    )


def test_controls_require_confirmation_and_real_readback_without_replay(tmp_path: Path) -> None:
    db = Database(tmp_path / "profile")
    db.migrate()
    provider = Provider()

    async def run() -> None:
        controls = CameraControls(db, provider, lambda actor: True)
        camera_id = provider.cameras[0].id
        with pytest.raises(ApiError) as error:
            controls.submit(camera_id, request(False), "synthetic-actor")
        assert error.value.code == "DISABLE_CONFIRMATION_REQUIRED" and not provider.calls
        body = request(False, confirm_disable=True)
        queued = controls.submit(camera_id, body, "synthetic-actor")
        assert queued.state == "pending" and queued.observed is None
        assert controls.submit(camera_id, body, "synthetic-actor").id == queued.id
        await asyncio.gather(*controls.tasks.values())
        assert controls.get(queued.id).state == "unknown"
        assert provider.calls == [("network_armed", False)]
        provider.result = False
        confirmed = await controls.verify(queued.id)
        assert confirmed.state == "confirmed" and confirmed.observed is False
        assert len(provider.calls) == 1 and provider.verifications == 1
        with pytest.raises(ApiError) as error:
            controls.submit(camera_id, request(True), "synthetic-actor")
        assert error.value.code == "CAMERA_CONTROL_WAIT"
        provider.cameras[0].motion_control = False
        with db.session() as session:
            session.get(CameraCommand, queued.id).created_at = (
                datetime.now(UTC) - timedelta(seconds=15)
            ).isoformat()
            session.commit()
        with pytest.raises(ApiError) as error:
            controls.submit(
                camera_id,
                CameraCommandRequest(
                    request_id=str(uuid4()), operation="motion_enabled", desired=True
                ),
                "synthetic-actor",
            )
        assert error.value.code == "CONTROL_UNVERIFIED"
        await controls.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_cancel_restart_and_expired_session_never_replay_mutation(tmp_path: Path) -> None:
    db = Database(tmp_path / "profile")
    db.migrate()
    provider = Provider()

    async def run() -> None:
        provider.wait = asyncio.Event()
        controls = CameraControls(db, provider, lambda actor: True)
        queued = controls.submit(provider.cameras[0].id, request(), "synthetic")
        await asyncio.sleep(0)
        assert provider.calls
        await controls.close()
        assert controls.get(queued.id).safe_error == "STOPPED_BEFORE_READBACK"
        with db.session() as session:
            row = session.get(CameraCommand, queued.id)
            row.state = "sending"
            row.created_at = (datetime.now(UTC) - timedelta(seconds=15)).isoformat()
            session.commit()
        restarted = CameraControls(db, provider, lambda actor: False)
        assert restarted.get(queued.id).state == "unknown" and not restarted.tasks
        expired = restarted.submit(provider.cameras[0].id, request(), "expired")
        await asyncio.gather(*restarted.tasks.values())
        assert restarted.get(expired.id).safe_error == "SESSION_EXPIRED"
        assert len(provider.calls) == 1
        await restarted.close()

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_authenticated_api_exposes_pending_then_confirmed_state(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    provider = Provider()
    provider.result = True
    client.app.state.controls = CameraControls(client.app.state.db, provider, lambda actor: True)
    route = f"/api/v1/cameras/{provider.cameras[0].id}/commands"
    assert client.get(f"{route}/latest").json() is None
    body = request().model_dump()
    assert client.post(route, json=body).status_code == 403
    response = client.post(route, headers=headers, json=body)
    assert response.status_code == 202, response.text
    status = client.get(f"/api/v1/camera-commands/{response.json()['id']}")
    assert status.json()["state"] == "confirmed"
    assert client.get(f"{route}/latest").json()["id"] == response.json()["id"]
    assert (
        client.get(f"{route}/latest?operation=network_armed").json()["id"] == response.json()["id"]
    )
    assert client.get(f"{route}/latest?operation=motion_enabled").json() is None
    assert client.get(f"{route}/latest?operation=unknown").status_code == 422
    assert len(provider.calls) == 1
    assert client.post(route, headers=headers, json=body).json()["state"] == "confirmed"
    assert len(provider.calls) == 1
    client.cookies.clear()
    assert client.get(f"/api/v1/camera-commands/{response.json()['id']}").status_code == 401
    assert client.get(f"{route}/latest?operation=network_armed").status_code == 401
