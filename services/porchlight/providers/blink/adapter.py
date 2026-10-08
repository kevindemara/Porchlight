from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4, uuid5

from aiohttp import ClientSession, ClientTimeout, TraceConfig
from blinkpy import api as upstream_api
from blinkpy.auth import Auth, BlinkTwoFARequiredError, LoginError, UnauthorizedError
from blinkpy.blinkpy import Blink

from porchlight.api.contracts import (
    ApiError,
    BlinkCredentials,
    BlinkStatus,
    BlinkVerification,
    CameraView,
    LocalModuleView,
    RelayTrustRequired,
)
from porchlight.providers.base import RecordingPage
from porchlight.providers.blink.live import BlinkLiveInput, relay_target
from porchlight.providers.blink.recordings import media_path as validate_media_path
from porchlight.providers.blink.recordings import normalize_page, retry_delay
from porchlight.security.vault import SecretStore
from porchlight.storage.database import Database
from porchlight.storage.models import IntegrationState


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


class BlinkAdapter:
    """One serialized account actor for inventory, recording and live commands."""

    def __init__(self, db: Database, vault: SecretStore):
        self.db, self.vault = db, vault
        self.lock = asyncio.Lock()
        self.session: ClientSession | None = None
        self.blink: Any = None
        self.status = BlinkStatus(
            state="not_configured", message="Connect your Blink account locally."
        )
        self.cameras: list[CameraView] = []
        self.challenge_actor: str | None = None
        self.challenge_expiry = 0.0
        self.verify_attempts = 0
        self.last_login = 0.0
        self.last_inventory = 0.0
        self.namespace = str(uuid4())
        self.hardware_id = str(uuid4()).upper()
        self.camera_ids: dict[str, list[str]] = {}
        self.live_cameras: dict[str, dict[str, Any]] = {}
        self.control_cameras: dict[str, dict[str, Any]] = {}
        self.local_modules: list[LocalModuleView] = []
        self.local_targets: dict[str, dict[str, Any]] = {}
        self.live_certificates: dict[str, str] = {}
        self.pending_live_certificates: dict[str, str] = {}
        self.request_count = 0
        with db.session() as session:
            pinned = session.get(IntegrationState, "blink_live_certificates")
            if pinned:
                self.live_certificates = dict(pinned.values.get("certificates", {}))
            cached = session.get(IntegrationState, "blink")
            if cached:
                self.cameras = [
                    CameraView.model_validate(camera) for camera in cached.values.get("cameras", [])
                ]
                self.last_inventory = float(cached.values.get("last_inventory", 0))
        # The upstream logs can contain raw account bodies, signed URLs and auth errors.
        # Stop those logger records at creation, including descendant loggers.
        for name in [
            "blinkpy",
            "blinkpy.auth",
            "blinkpy.api",
            "blinkpy.blinkpy",
            "blinkpy.helpers.util",
            "blinkpy.sync_module",
            "blinkpy.camera",
            "blinkpy.livestream",
        ]:
            logging.getLogger(name).disabled = True
        root_logger = logging.getLogger("blinkpy")
        root_logger.addHandler(logging.NullHandler())
        root_logger.propagate = False

    async def connection(self, data: dict[str, Any]) -> None:
        if self.session:
            await self.session.close()
        trace = TraceConfig()

        async def request_finished(_: Any, __: Any, params: Any) -> None:
            self.request_count += 1
            if params.response.status == 429:
                params.response.release()
                raise ApiError(
                    429,
                    "BLINK_RATE_LIMITED",
                    "Blink asked Porchlight to wait.",
                    True,
                    retry_delay(params.response.headers.get("Retry-After")),
                )

        trace.on_request_end.append(request_finished)
        self.session = ClientSession(
            timeout=ClientTimeout(total=45), trust_env=False, trace_configs=[trace]
        )
        self.blink = Blink(refresh_rate=120, session=self.session)
        self.blink.auth = Auth(data, no_prompt=True, session=self.session)

    def remove_transient_credentials(self) -> None:
        if self.blink:
            self.blink.auth.data.pop("password", None)
            self.blink.auth.data.pop("2fa_code", None)

    def persist(self) -> None:
        self.remove_transient_credentials()
        attrs = dict(self.blink.auth.login_attributes)
        attrs.pop("password", None)
        attrs.pop("2fa_code", None)
        self.vault.write(
            {"namespace": self.namespace, "hardware_id": self.hardware_id, "auth": attrs}
        )

    async def begin_auth(self, credentials: BlinkCredentials, actor: str) -> BlinkStatus:
        async with self.lock:
            if time.monotonic() - self.last_login < 60:
                raise ApiError(
                    429,
                    "BLINK_LOGIN_THROTTLED",
                    "Wait a minute before starting another Blink sign-in.",
                    True,
                )
            saved = self.vault.read()
            if saved:
                self.namespace = saved.get("namespace", self.namespace)
                self.hardware_id = saved.get("hardware_id", self.hardware_id)
            # Prove the vault can encrypt before sending any Blink credentials.
            self.vault.write(
                saved or {"namespace": self.namespace, "hardware_id": self.hardware_id}
            )
            self.last_login = time.monotonic()
            self.status = BlinkStatus(state="authenticating", message="Signing in to Blink.")
            await self.connection(
                {
                    "username": credentials.email,
                    "password": credentials.password.get_secret_value(),
                    "hardware_id": self.hardware_id,
                }
            )
            try:
                await self.blink.auth.startup()
            except BlinkTwoFARequiredError:
                self.challenge_actor = actor
                self.challenge_expiry = time.time() + 10 * 60
                self.verify_attempts = 0
                self.status = BlinkStatus(
                    state="challenge_required",
                    message="Enter the verification code sent by Blink.",
                    challenge_id=str(uuid4()),
                    challenge_expires_at=iso(self.challenge_expiry),
                )
                return self.status
            except (LoginError, UnauthorizedError):
                self.status = BlinkStatus(
                    state="invalid_credentials",
                    message="Blink could not complete sign-in. Check your details or try later.",
                )
                return self.status
            except Exception:
                self.status = BlinkStatus(
                    state="service_unavailable", message="Blink sign-in is temporarily unavailable."
                )
                return self.status
            finally:
                self.remove_transient_credentials()
            await self.connected()
            return self.status

    async def complete_auth(self, verification: BlinkVerification, actor: str) -> BlinkStatus:
        async with self.lock:
            if (
                self.status.state != "challenge_required"
                or actor != self.challenge_actor
                or verification.challenge_id != self.status.challenge_id
            ):
                raise ApiError(
                    409, "INVALID_CHALLENGE", "Start Blink sign-in again in this browser."
                )
            if time.time() >= self.challenge_expiry or self.verify_attempts >= 5:
                self.status = BlinkStatus(
                    state="reauth_required",
                    message="The local verification session expired. Sign in again.",
                )
                raise ApiError(409, "CHALLENGE_EXPIRED", self.status.message)
            self.verify_attempts += 1
            try:
                success = await self.blink.auth.complete_2fa_login(
                    verification.code.get_secret_value()
                )
            except Exception as exc:
                raise ApiError(
                    503, "VERIFICATION_UNAVAILABLE", "Blink could not verify the code. Try later."
                ) from exc
            if not success:
                raise ApiError(422, "INVALID_CODE", "Blink did not accept this verification code.")
            self.challenge_actor = None
            await self.connected()
            return self.status

    async def connected(self) -> None:
        self.persist()
        try:
            await self.read_inventory()
            self.status = BlinkStatus(
                state="connected",
                message="Signed in. Recording retrieval and no-plan access remain unverified.",
                camera_count=len(self.cameras),
                inventory_checked_at=iso(self.last_inventory),
                next_refresh_at=iso(self.last_inventory + 120),
            )
        except Exception:
            self.status = BlinkStatus(
                state="service_unavailable",
                message="Signed in, but inventory could not be read. Try refreshing later.",
            )

    async def read_inventory(self) -> None:
        self.blink.setup_urls()
        await self.blink.get_homescreen()
        home = self.blink.homescreen
        if (
            not isinstance(home, dict)
            or not isinstance(home.get("networks"), list)
            or not any(key in home for key in ("cameras", "owls", "doorbells"))
            or any(
                not isinstance(home.get(key, []), list) for key in ("cameras", "owls", "doorbells")
            )
            or not isinstance(home.get("sync_modules", []), list)
        ):
            raise ValueError("Unexpected homescreen contract")
        networks = {str(network.get("id")): network for network in home.get("networks", [])}
        cameras: list[CameraView] = []
        camera_ids: dict[str, list[str]] = {}
        live_cameras: dict[str, dict[str, Any]] = {}
        control_cameras: dict[str, dict[str, Any]] = {}
        for collection in ["cameras", "owls", "doorbells"]:
            for camera in home.get(collection, []):
                if camera.get("id") is None:
                    continue
                network = networks.get(str(camera.get("network_id")), {})
                armed = network.get("armed")
                motion = camera.get("enabled")
                temperature = (
                    camera.get("signals", {}).get("temp")
                    if isinstance(camera.get("signals"), dict)
                    else camera.get("temperature")
                )
                temperature_c = (
                    (temperature - 32) / 1.8 if type(temperature) in {int, float} else None
                )
                if temperature_c is not None and not -50 <= temperature_c <= 80:
                    temperature_c = None
                battery = camera.get("battery_state") or camera.get("battery")
                cameras.append(
                    CameraView(
                        id=str(uuid5(UUID(self.namespace), f"{collection}:{camera['id']}")),
                        name=str(camera.get("name", "Unnamed camera"))[:120],
                        family=collection,
                        network_name=str(network.get("name", "Unknown network"))[:120],
                        network_id=str(uuid5(UUID(self.namespace), f"network:{network['id']}"))
                        if network and network.get("id") is not None
                        else None,
                        observed_armed=armed if isinstance(armed, bool) else None,
                        observed_motion=motion if isinstance(motion, bool) else None,
                        observed_at=iso(time.time()),
                        network_control=isinstance(armed, bool) and bool(network),
                        motion_control=isinstance(motion, bool) and bool(network),
                        battery_state=battery
                        if isinstance(battery, str) and battery in {"ok", "good", "low", "unknown"}
                        else None,
                        temperature_c=round(temperature_c, 1)
                        if temperature_c is not None
                        else None,
                    )
                )
                camera_ids.setdefault(str(camera["id"]), []).append(cameras[-1].id)
                if camera.get("network_id") is not None and network:
                    control_cameras[cameras[-1].id] = {
                        "id": camera["id"],
                        "network_id": camera["network_id"],
                        "type": {"cameras": "", "owls": "owl", "doorbells": "doorbell"}[collection],
                    }
                if camera.get("network_id") is not None and isinstance(camera.get("serial"), str):
                    live_cameras[cameras[-1].id] = {
                        "id": camera["id"],
                        "network_id": camera["network_id"],
                        "serial": camera["serial"],
                        "type": {"cameras": "", "owls": "owl", "doorbells": "doorbell"}[collection],
                    }
                    cameras[-1] = cameras[-1].model_copy(update={"live_view": "experimental"})
        self.cameras = cameras
        self.camera_ids = camera_ids
        self.live_cameras = live_cameras
        self.control_cameras = control_cameras
        self.local_modules, self.local_targets = [], {}
        for module in home.get("sync_modules", []):
            if (
                not isinstance(module, dict)
                or not str(module.get("id", "")).isdigit()
                or not str(module.get("network_id", "")).isdigit()
            ):
                continue
            identifier = str(uuid5(UUID(self.namespace), f"module:{module['id']}"))
            ready = (
                module.get("local_storage_enabled") is True
                and module.get("local_storage_compatible") is True
                and module.get("local_storage_status") == "active"
            )
            self.local_modules.append(
                LocalModuleView(
                    id=identifier,
                    name=str(module.get("name", "Sync Module"))[:120],
                    storage_ready=ready,
                    message=(
                        "API reports compatible, active local storage. "
                        "Retrieval needs hardware testing."
                    )
                    if ready
                    else (
                        "Compatible, active local storage has not been reported. "
                        "Core cannot record to removable storage."
                    ),
                    checked_at=iso(time.time()),
                )
            )
            if ready:
                self.local_targets[identifier] = {
                    "id": module["id"],
                    "network_id": module["network_id"],
                }
        self.last_inventory = time.time()
        with self.db.session() as db:
            row = db.get(IntegrationState, "blink")
            values = {
                "cameras": [camera.model_dump() for camera in cameras],
                "last_inventory": self.last_inventory,
            }
            if row:
                row.values = values
            else:
                db.add(IntegrationState(id="blink", values=values))
            db.commit()
        self.persist()

    async def discover_inventory(self) -> list[CameraView]:
        async with self.lock:
            if self.status.state not in {"connected", "service_unavailable"} or not self.blink:
                raise ApiError(409, "BLINK_AUTH_REQUIRED", "Connect your Blink account first.")
            if time.time() - self.last_inventory < 120:
                return self.cameras
            try:
                await self.refresh_if_needed()
                await self.read_inventory()
            except ApiError:
                raise
            except Exception as exc:
                raise ApiError(
                    503, "BLINK_UNAVAILABLE", "Blink inventory could not be refreshed.", True
                ) from exc
            self.status = self.status.model_copy(
                update={
                    "state": "connected",
                    "camera_count": len(self.cameras),
                    "inventory_checked_at": iso(self.last_inventory),
                    "next_refresh_at": iso(self.last_inventory + 120),
                }
            )
            return self.cameras

    async def refresh_if_needed(self) -> None:
        auth = self.blink.auth
        if not auth.need_refresh():
            return
        tokens = await upstream_api.oauth_refresh_token(auth, auth.refresh_token, auth.hardware_id)
        if not tokens or not tokens.get("access_token"):
            self.status = BlinkStatus(
                state="reauth_required", message="Blink requires a fresh sign-in."
            )
            raise ApiError(409, "BLINK_AUTH_REQUIRED", self.status.message)
        auth.token = tokens["access_token"]
        auth.refresh_token = tokens.get("refresh_token", auth.refresh_token)
        auth.expires_in = tokens.get("expires_in", 3600)
        auth.expiration_date = time.time() + auth.expires_in
        self.persist()

    async def restore_session(self) -> None:
        async with self.lock:
            try:
                saved = self.vault.read()
                if not saved or not saved.get("auth"):
                    return
                self.namespace = saved["namespace"]
                self.hardware_id = saved["hardware_id"]
                await self.connection(saved["auth"])
                await self.refresh_if_needed()
                await self.connected()
            except ApiError as exc:
                self.status = BlinkStatus(
                    state="vault_unavailable"
                    if exc.code == "VAULT_UNAVAILABLE"
                    else "reauth_required",
                    message=exc.message,
                )
            except Exception:
                self.status = BlinkStatus(
                    state="reauth_required",
                    message="The saved Blink session could not be restored. Sign in again.",
                )

    async def close(self) -> None:
        self.remove_transient_credentials()
        if self.session:
            await self.session.close()

    def observed_state(self, camera_id: str, operation: str) -> bool | None:
        if operation not in {"network_armed", "motion_enabled"}:
            return None
        camera = next((camera for camera in self.cameras if camera.id == camera_id), None)
        if not camera:
            return None
        return camera.observed_armed if operation == "network_armed" else camera.observed_motion

    async def verify_camera_state(self, camera_id: str, operation: str) -> bool | None:
        if operation not in {"network_armed", "motion_enabled"}:
            raise ApiError(422, "INVALID_CONTROL", "Choose a supported camera control.")
        async with self.lock:
            if not self.blink or self.status.state != "connected":
                raise ApiError(
                    409, "BLINK_AUTH_REQUIRED", "Reconnect Blink to verify camera state."
                )
            await self.refresh_if_needed()
            await self.read_inventory()
            return self.observed_state(camera_id, operation)

    async def set_camera_state(
        self,
        camera_id: str,
        operation: str,
        desired: bool,
        is_authorized: Callable[[], bool] | None = None,
    ) -> bool | None:
        if operation not in {"network_armed", "motion_enabled"}:
            raise ApiError(422, "INVALID_CONTROL", "Choose a supported camera control.")
        async with self.lock:
            if not self.blink or self.status.state != "connected":
                raise ApiError(
                    409, "BLINK_AUTH_REQUIRED", "Reconnect Blink before changing camera state."
                )
            camera = self.control_cameras.get(camera_id)
            if not camera:
                raise ApiError(409, "CONTROL_UNVERIFIED", "This camera's control is unavailable.")
            await self.refresh_if_needed()
            # Read current state first, so an already-satisfied command sends no mutation.
            await self.read_inventory()
            camera = self.control_cameras.get(camera_id)
            if not camera:
                raise ApiError(
                    409, "CONTROL_UNVERIFIED", "The camera's connection changed. Refresh first."
                )
            observed = self.observed_state(camera_id, operation)
            if is_authorized is not None and not is_authorized():
                raise ApiError(
                    401, "SESSION_EXPIRED", "Sign in again before changing camera state."
                )
            if observed is None:
                raise ApiError(
                    409, "CONTROL_UNVERIFIED", "Blink did not expose a readable control state."
                )
            if observed == desired:
                return observed
            if operation == "network_armed":
                call = (
                    upstream_api.request_system_arm
                    if desired
                    else upstream_api.request_system_disarm
                )
                await call(self.blink, camera["network_id"])
            elif operation == "motion_enabled":
                call = (
                    upstream_api.request_motion_detection_enable
                    if desired
                    else upstream_api.request_motion_detection_disable
                )
                await call(
                    self.blink, camera["network_id"], camera["id"], camera_type=camera["type"]
                )
            else:
                raise ApiError(422, "INVALID_CONTROL", "Choose a supported camera control.")
            await self.read_inventory()
            return self.observed_state(camera_id, operation)

    async def open_live(self, camera_id: str) -> BlinkLiveInput:
        async with self.lock:
            if not self.blink or self.status.state != "connected":
                raise ApiError(
                    409, "BLINK_AUTH_REQUIRED", "Connect Blink before opening live view."
                )
            camera = self.live_cameras.get(camera_id)
            if not camera:
                raise ApiError(409, "LIVE_UNSUPPORTED", "Live view is unavailable for this camera.")
            await self.refresh_if_needed()
            response: Any = None
            live: BlinkLiveInput | None = None
            try:
                response = await upstream_api.request_camera_liveview(
                    self.blink, camera["network_id"], camera["id"], camera_type=camera["type"]
                )
                if not isinstance(response, dict) or not isinstance(response.get("server"), str):
                    raise ApiError(409, "LIVE_UNSUPPORTED", "Blink did not provide a live stream.")
                relay_target(response["server"])
                if not isinstance(response.get("command_id"), int) or not isinstance(
                    response.get("polling_interval"), (int, float)
                ):
                    raise ApiError(409, "LIVE_UNSUPPORTED", "Blink's live response is unsupported.")
                proxy = SimpleNamespace(
                    serial=camera["serial"],
                    network_id=camera["network_id"],
                    sync=SimpleNamespace(blink=self.blink),
                )
                live = BlinkLiveInput(proxy, response, self.lock, self.live_certificates)
            except ApiError:
                raise
            except Exception as exc:
                raise ApiError(
                    503, "LIVE_START_FAILED", "Blink could not start live view.", True
                ) from exc
            finally:
                if (
                    live is None
                    and isinstance(response, dict)
                    and isinstance(response.get("command_id"), int)
                ):
                    try:
                        async with asyncio.timeout(3):
                            await upstream_api.request_command_done(
                                self.blink, camera["network_id"], response["command_id"]
                            )
                    except Exception:
                        pass
        # Do not hold the actor lock during relay I/O or cleanup's command-done request.
        try:
            await live.start()
            return live
        except RelayTrustRequired as error:
            self.pending_live_certificates = {error.fingerprint: error.pem}
            raise
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(
                503, "LIVE_CONNECT_FAILED", "The live relay could not be reached.", True
            ) from exc

    def trust_live_certificate(self, fingerprint: str) -> None:
        pem = self.pending_live_certificates.get(fingerprint)
        if not pem:
            raise ApiError(
                409, "LIVE_CERT_CHANGED", "Start live view again to review its certificate."
            )
        self.live_certificates[fingerprint] = pem
        # Keep trust bounded and scoped to the application, never the OS certificate store.
        self.live_certificates = dict(list(self.live_certificates.items())[-8:])
        with self.db.session() as db:
            row = db.get(IntegrationState, "blink_live_certificates")
            if not row:
                row = IntegrationState(id="blink_live_certificates", values={})
                db.add(row)
            row.values = {"certificates": self.live_certificates}
            db.commit()
        self.pending_live_certificates = {}

    def revoke_live_certificates(self) -> None:
        self.live_certificates = {}
        self.pending_live_certificates = {}
        with self.db.session() as db:
            row = db.get(IntegrationState, "blink_live_certificates")
            if row:
                db.delete(row)
                db.commit()

    @property
    def recording_source_id(self) -> str:
        if not self.blink or self.status.state != "connected":
            raise ApiError(409, "BLINK_AUTH_REQUIRED", "Connect Blink before syncing recordings.")
        return str(uuid5(UUID(self.namespace), f"cloud:{self.blink.account_id}"))

    async def recording_page(self, since: float, page: int) -> RecordingPage:
        async with self.lock:
            _ = self.recording_source_id
            await self.refresh_if_needed()
            try:
                response = await upstream_api.request_videos(self.blink, time=since, page=page)
                clips = normalize_page(
                    response, self.namespace, str(self.blink.account_id), self.camera_ids
                )
                return RecordingPage(clips=clips, exhausted=len(response["media"]) == 0)
            except ApiError:
                raise
            except UnauthorizedError as exc:
                self.status = BlinkStatus(
                    state="reauth_required", message="Blink requires a fresh sign-in."
                )
                raise ApiError(409, "BLINK_AUTH_REQUIRED", self.status.message) from exc
            except Exception as exc:
                raise ApiError(
                    503,
                    "RECORDING_LIST_UNAVAILABLE",
                    "Blink's recording list could not be read.",
                    True,
                ) from exc

    async def download_recording(self, media_path: str, destination: Path) -> None:
        async with self.lock:
            await self.download_locked(media_path, destination)

    async def download_locked(self, media_path: str, destination: Path) -> None:
        _ = self.recording_source_id
        await self.refresh_if_needed()
        path = validate_media_path(media_path)
        base = urlsplit(self.blink.urls.base_url)
        if (
            base.scheme != "https"
            or not base.hostname
            or not base.hostname.endswith(".immedia-semi.com")
            or not base.hostname.startswith("rest-")
        ):
            raise ApiError(503, "MEDIA_HOST_REJECTED", "Blink returned an unsupported media host.")
        if not self.session:
            raise ApiError(409, "BLINK_AUTH_REQUIRED", "Connect Blink first.")
        try:
            async with self.session.get(
                self.blink.urls.base_url + path,
                headers=self.blink.auth.header,
                allow_redirects=False,
                timeout=ClientTimeout(total=90),
            ) as response:
                if response.status in {401, 403}:
                    self.status = BlinkStatus(
                        state="reauth_required", message="Blink requires a fresh sign-in."
                    )
                    raise ApiError(409, "BLINK_AUTH_REQUIRED", "Blink requires a fresh sign-in.")
                if response.status in {404, 410}:
                    raise ApiError(
                        410,
                        "SOURCE_MEDIA_EXPIRED",
                        "This recording is no longer available from Blink.",
                    )
                if response.status == 429:
                    raise ApiError(
                        429,
                        "BLINK_RATE_LIMITED",
                        "Blink asked Porchlight to wait before downloading.",
                        True,
                        retry_delay(response.headers.get("Retry-After")),
                    )
                if 300 <= response.status < 400:
                    raise ApiError(
                        503,
                        "MEDIA_REDIRECT_UNVERIFIED",
                        "This Blink media redirect requires compatibility validation.",
                    )
                if response.status != 200:
                    raise ApiError(
                        503,
                        "CLIP_TRANSFER_FAILED",
                        "Blink could not transfer this recording.",
                        True,
                    )
                total = 0
                with destination.open("xb") as handle:
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        total += len(chunk)
                        if total > 256 * 1024 * 1024:
                            raise ApiError(
                                413,
                                "MEDIA_TOO_LARGE",
                                "The recording exceeds the 256 MiB limit.",
                            )
                        handle.write(chunk)
                    handle.flush()
                    import os

                    os.fsync(handle.fileno())
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(
                503,
                "CLIP_TRANSFER_FAILED",
                "The recording transfer failed. Porchlight will retry within its limits.",
                True,
            ) from exc
