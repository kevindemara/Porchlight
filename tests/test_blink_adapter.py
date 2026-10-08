import asyncio
import inspect
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from porchlight.api.contracts import ApiError, BlinkCredentials, BlinkStatus, BlinkVerification
from porchlight.providers.blink import adapter
from porchlight.security.vault import WindowsVault
from porchlight.storage.database import Database
from pydantic import SecretStr


class SyntheticVault:
    def __init__(self) -> None:
        self.value: dict[str, Any] | None = None

    def read(self) -> dict[str, Any] | None:
        return self.value

    def write(self, value: dict[str, Any]) -> None:
        self.value = value


class SyntheticAuth:
    def __init__(self, data: dict[str, Any], **kwargs: Any):
        assert kwargs["no_prompt"] is True
        self.data = data

    async def startup(self) -> None:
        raise adapter.BlinkTwoFARequiredError

    async def complete_2fa_login(self, code: str) -> bool:
        return code == "123456"

    @property
    def login_attributes(self) -> dict[str, Any]:
        return {**self.data, "token": "synthetic-token", "refresh_token": "synthetic-refresh"}


class SyntheticBlink:
    def __init__(self, **kwargs: Any):
        assert kwargs["refresh_rate"] == 120
        self.auth: Any = None
        self.homescreen = {
            "networks": [{"id": 1, "name": "Synthetic network", "armed": True}],
            "cameras": [
                {"id": 1, "name": "Synthetic camera", "network_id": 1},
                {"id": 2, "name": "Synthetic camera", "network_id": 1},
            ],
        }

    def setup_urls(self) -> None:
        pass

    async def get_homescreen(self) -> None:
        pass


def test_real_pinned_signatures_have_noninteractive_auth() -> None:
    assert "no_prompt" in inspect.signature(adapter.Auth).parameters
    assert "twofa_code" in inspect.signature(adapter.Auth.complete_2fa_login).parameters
    assert inspect.iscoroutinefunction(adapter.Auth.startup)
    assert inspect.iscoroutinefunction(adapter.upstream_api.oauth_refresh_token)


def test_auth_challenge_is_bound_and_password_not_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adapter, "Auth", SyntheticAuth)
    monkeypatch.setattr(adapter, "Blink", SyntheticBlink)
    db = Database(tmp_path / "db")
    db.migrate()
    vault = SyntheticVault()

    async def exercise() -> None:
        provider = adapter.BlinkAdapter(db, vault)
        try:
            status = await provider.begin_auth(
                BlinkCredentials(
                    email="synthetic@example.test", password=SecretStr("synthetic-password")
                ),
                "browser-one",
            )
            assert status.state == "challenge_required"
            assert "password" not in provider.blink.auth.data
            verification = BlinkVerification(
                challenge_id=status.challenge_id or "", code=SecretStr("123456")
            )
            with pytest.raises(ApiError):
                await provider.complete_auth(verification, "browser-two")
            connected = await provider.complete_auth(verification, "browser-one")
            assert connected.state == "connected"
            assert connected.recording_access == "unverified"
            assert connected.entitlement == "unknown"
            assert len(provider.cameras) == 2
            assert provider.cameras[0].id != provider.cameras[1].id
            network_id = provider.cameras[0].network_id
            assert network_id and network_id == provider.cameras[1].network_id
            identifier = provider.cameras[0].id
            provider.blink.homescreen["cameras"][0]["name"] = "Renamed synthetic camera"
            await provider.read_inventory()
            assert provider.cameras[0].id == identifier
            assert provider.cameras[0].network_id == network_id
            provider.blink.homescreen["networks"].append(
                {"id": 2, "name": "Synthetic network", "armed": False}
            )
            provider.blink.homescreen["cameras"][1]["network_id"] = 2
            await provider.read_inventory()
            assert provider.cameras[0].network_name == provider.cameras[1].network_name
            assert provider.cameras[0].network_id != provider.cameras[1].network_id
            assert "synthetic-password" not in str(vault.value)
            assert "123456" not in str(vault.value)
            provider.blink.homescreen = {"error": "synthetic upstream failure"}
            with pytest.raises(ValueError):
                await provider.read_inventory()
            assert provider.cameras[0].id == identifier
        finally:
            await provider.close()

    asyncio.run(exercise())
    db.close()


def test_expired_challenge_does_not_call_upstream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adapter, "Auth", SyntheticAuth)
    monkeypatch.setattr(adapter, "Blink", SyntheticBlink)
    db = Database(tmp_path / "db")
    db.migrate()

    async def exercise() -> None:
        provider = adapter.BlinkAdapter(db, SyntheticVault())
        try:
            status = await provider.begin_auth(
                BlinkCredentials(
                    email="synthetic@example.test", password=SecretStr("synthetic-password")
                ),
                "browser",
            )
            provider.challenge_expiry = time.time() - 1
            with pytest.raises(ApiError) as error:
                await provider.complete_auth(
                    BlinkVerification(
                        challenge_id=status.challenge_id or "", code=SecretStr("123456")
                    ),
                    "browser",
                )
            assert error.value.code == "CHALLENGE_EXPIRED"
        finally:
            await provider.close()

    asyncio.run(exercise())
    db.close()


def test_windows_vault_encrypts_and_fails_closed(tmp_path: Path) -> None:
    vault = WindowsVault(tmp_path)
    vault.write({"test": "SYNTHETIC-PRIVATE-SESSION"})
    assert b"SYNTHETIC-PRIVATE-SESSION" not in vault.path.read_bytes()
    assert vault.read() == {"test": "SYNTHETIC-PRIVATE-SESSION"}
    vault.path.write_bytes(b"corrupt envelope")
    with pytest.raises(ApiError) as error:
        vault.read()
    assert error.value.code == "VAULT_UNAVAILABLE"


def test_media_redirect_is_never_followed_or_forwarded_credentials(tmp_path: Path) -> None:
    db = Database(tmp_path / "db")
    db.migrate()
    calls: list[dict[str, Any]] = []

    class Redirect:
        status = 302

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

    class Session:
        def get(self, url: str, **kwargs: Any) -> Redirect:
            calls.append({"url": url, **kwargs})
            return Redirect()

    async def exercise() -> None:
        provider = adapter.BlinkAdapter(db, SyntheticVault())
        provider.status = BlinkStatus(state="connected", message="Synthetic connected")
        provider.blink = SimpleNamespace(
            account_id="synthetic-account",
            auth=SimpleNamespace(header={"Authorization": "Bearer synthetic"}),
            urls=SimpleNamespace(base_url="https://rest-prod.immedia-semi.com"),
        )
        provider.session = Session()  # type: ignore[assignment]
        provider.refresh_if_needed = AsyncMock()  # type: ignore[method-assign]
        with pytest.raises(ApiError) as error:
            await provider.download_recording("/api/v2/media/synthetic.mp4", tmp_path / "clip.part")
        assert error.value.code == "MEDIA_REDIRECT_UNVERIFIED"

    asyncio.run(exercise())
    assert len(calls) == 1 and calls[0]["allow_redirects"] is False
    assert not (tmp_path / "clip.part").exists()
    db.close()


@pytest.mark.parametrize(
    "family,camera_type", [("cameras", ""), ("owls", "owl"), ("doorbells", "doorbell")]
)
def test_manual_controls_map_ids_and_require_observed_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, family: str, camera_type: str
) -> None:
    db = Database(tmp_path / "db")
    db.migrate()

    async def exercise() -> None:
        provider = adapter.BlinkAdapter(db, SyntheticVault())
        provider.status = BlinkStatus(state="connected", message="Synthetic connected")
        blink = SyntheticBlink(refresh_rate=120)
        blink.auth = SimpleNamespace(data={}, login_attributes={"token": "synthetic"})
        camera = {
            "id": 7,
            "network_id": 3,
            "name": "Synthetic",
            "enabled": True,
            "battery": "ok",
            "signals": {"temp": 68},
        }
        network = {"id": 3, "name": "Synthetic network", "armed": True}
        blink.homescreen = {"networks": [network], family: [camera]}
        provider.blink = blink  # type: ignore[assignment]
        provider.refresh_if_needed = AsyncMock()  # type: ignore[method-assign]
        reads = 0

        async def inventory() -> None:
            nonlocal reads
            reads += 1

        blink.get_homescreen = inventory  # type: ignore[method-assign]
        await provider.read_inventory()
        identifier = provider.cameras[0].id
        assert provider.cameras[0].temperature_c == 20
        assert provider.cameras[0].battery_state == "ok"
        assert provider.cameras[0].observed_motion is True
        calls: list[tuple[str, int, int | None, str | None]] = []

        async def disable(
            blink_arg: object, network_id: int, camera_id: int, **kwargs: Any
        ) -> None:
            assert blink_arg is blink
            calls.append(("motion", network_id, camera_id, kwargs["camera_type"]))
            camera["enabled"] = False

        async def disarm(blink_arg: object, network_id: int) -> None:
            assert blink_arg is blink
            calls.append(("network", network_id, None, None))
            network["armed"] = False

        monkeypatch.setattr(adapter.upstream_api, "request_motion_detection_disable", disable)
        monkeypatch.setattr(adapter.upstream_api, "request_system_disarm", disarm)
        assert await provider.set_camera_state(identifier, "motion_enabled", False) is False
        assert calls == [("motion", 3, 7, camera_type)]
        assert await provider.set_camera_state(identifier, "motion_enabled", False) is False
        assert len(calls) == 1  # Already satisfied after a fresh read: no repeated mutation.
        assert await provider.set_camera_state(identifier, "network_armed", False) is False
        assert calls[-1] == ("network", 3, None, None)
        assert await provider.verify_camera_state(identifier, "network_armed") is False
        assert len(calls) == 2
        previous_reads = reads
        with pytest.raises(ApiError):
            await provider.set_camera_state(identifier, "unsupported", False)
        assert reads == previous_reads and len(calls) == 2
        with pytest.raises(ApiError) as error:
            await provider.set_camera_state(identifier, "motion_enabled", True, lambda: False)
        assert error.value.code == "SESSION_EXPIRED" and len(calls) == 2
        camera["battery"] = {"secret": "synthetic"}
        camera["signals"] = {"temp": float("nan")}
        camera["enabled"] = "unknown"
        await provider.read_inventory()
        assert provider.cameras[0].temperature_c is None
        assert provider.cameras[0].battery_state is None
        assert not provider.cameras[0].motion_control
        with pytest.raises(ApiError) as error:
            await provider.set_camera_state(identifier, "motion_enabled", True)
        assert error.value.code == "CONTROL_UNVERIFIED" and len(calls) == 2
        await provider.close()

    try:
        asyncio.run(exercise())
    finally:
        db.close()
