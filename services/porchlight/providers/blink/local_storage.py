"""Candidate local-module workflow over the pinned API; real hardware remains unverified."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from blinkpy import api as upstream_api
from blinkpy.auth import UnauthorizedError
from blinkpy.helpers.util import to_alphanumeric

from porchlight.api.contracts import ApiError, BlinkStatus
from porchlight.providers.base import ClipReference, RecordingPage
from porchlight.storage.models import IntegrationState

if TYPE_CHECKING:
    from porchlight.providers.blink.adapter import BlinkAdapter


def token(value: Any) -> str:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, str))
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", str(value))
    ):
        raise ApiError(
            503, "LOCAL_CONTRACT_CHANGED", "Blink returned unsupported local-storage metadata."
        )
    return str(value)


def normalize_manifest(
    body: Any,
    namespace: str,
    account: str,
    module_id: str,
    names: dict[str, list[str]],
) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(body, dict) or not isinstance(body.get("clips"), list):
        raise ApiError(503, "LOCAL_MANIFEST_UNAVAILABLE", "The module manifest is not ready.", True)
    manifest = token(body.get("manifest_id"))
    if len(body["clips"]) > 10000:
        raise ApiError(
            503,
            "LOCAL_MANIFEST_LIMIT",
            "This manifest exceeds the current safe processing limit. No checkpoint was advanced.",
        )
    clips: dict[str, dict[str, Any]] = {}
    for item in body["clips"]:
        if not isinstance(item, dict):
            raise ApiError(
                503, "LOCAL_CONTRACT_CHANGED", "Blink returned incomplete local clip metadata."
            )
        identifier = token(item.get("id"))
        name, raw_time, size = item.get("camera_name"), item.get("created_at"), item.get("size")
        if (
            not isinstance(name, str)
            or len(name) > 120
            or not isinstance(raw_time, str)
            or len(raw_time) > 100
            or type(size) is not int
            or not 0 <= size < 2**40
        ):
            raise ApiError(
                503, "LOCAL_CONTRACT_CHANGED", "Blink returned incomplete local clip metadata."
            )
        captured = None
        try:
            parsed = datetime.fromisoformat(raw_time)
            if parsed.tzinfo:
                captured = parsed.astimezone(UTC).isoformat()
        except ValueError:
            pass
        # Manifest generations are transient. Retain original timestamp/size and item ID;
        # there is no verified storage-volume generation in this upstream contract.
        key = str(
            uuid5(UUID(namespace), f"local:{account}:{module_id}:{identifier}:{raw_time}:{size}")
        )
        matches = names.get(name, [])
        clips[key] = {
            "key": key,
            "id": identifier,
            "camera_id": matches[0] if len(matches) == 1 else None,
            "captured_at": captured,
            "raw_timestamp": raw_time,
        }
    return manifest, list(clips.values())


class LocalStorageSource:
    def __init__(self, adapter: BlinkAdapter):
        self.adapter = adapter

    @property
    def recording_source_id(self) -> str:
        _ = self.adapter.recording_source_id  # Same connected account, separate durable source.
        return str(
            uuid5(UUID(self.adapter.namespace), f"local-account:{self.adapter.blink.account_id}")
        )

    @asynccontextmanager
    async def serialized(self) -> AsyncIterator[None]:
        async with self.adapter.lock:
            _ = self.recording_source_id
            try:
                await self.adapter.refresh_if_needed()
                yield
            except UnauthorizedError as exc:
                self.adapter.status = BlinkStatus(
                    state="reauth_required", message="Blink requires a fresh sign-in."
                )
                raise ApiError(
                    409, "BLINK_AUTH_REQUIRED", "Reconnect Blink before local-storage retrieval."
                ) from exc

    def state(self, module: str) -> dict[str, Any]:
        with self.adapter.db.session() as session:
            row = session.get(
                IntegrationState, f"local_manifest:{self.recording_source_id}:{module}"
            )
            return dict(row.values) if row else {}

    def save(self, module: str, values: dict[str, Any]) -> None:
        with self.adapter.db.session() as session:
            key = f"local_manifest:{self.recording_source_id}:{module}"
            row = session.get(IntegrationState, key)
            if not row:
                row = IntegrationState(id=key, values={})
                session.add(row)
            row.values = values
            session.commit()

    def camera_names(self, network: Any) -> dict[str, list[str]]:
        names: dict[str, list[str]] = {}
        for camera in self.adapter.cameras:
            raw = self.adapter.control_cameras.get(camera.id)
            if raw and str(raw["network_id"]) == str(network):
                names.setdefault(str(to_alphanumeric(camera.name)), []).append(camera.id)
        return names

    async def manifest_locked(self, module: str, *, refresh: bool) -> dict[str, Any]:
        target = self.adapter.local_targets.get(module)
        if not target:
            raise ApiError(
                409, "LOCAL_STORAGE_NOT_READY", "Compatible, active removable storage is required."
            )
        values = self.state(module)
        now = time.time()
        if values.get("clips") is not None and (
            not refresh or now - float(values.get("started", 0)) < 120
        ):
            return values
        request_id = values.get("request_id")
        if request_id is None or now - float(values.get("started", 0)) > 300:
            if now - float(values.get("started", 0)) < 120:
                raise ApiError(
                    429,
                    "LOCAL_MODULE_WAIT",
                    "Wait for the current module workflow before requesting another.",
                    True,
                    120,
                )
            values = {"started": now, "request_id": None}
            self.save(module, values)  # Durable intent prevents restart request storms.
            response = await upstream_api.request_local_storage_manifest(
                self.adapter.blink, target["network_id"], target["id"]
            )
            if not isinstance(response, dict) or response.get("id") is None:
                raise ApiError(
                    503,
                    "LOCAL_MANIFEST_UNAVAILABLE",
                    "The module did not accept a manifest request.",
                    True,
                )
            request_id = token(response["id"])
            values["request_id"] = request_id
            self.save(module, values)
        for attempt in range(4):
            response = await upstream_api.get_local_storage_manifest(
                self.adapter.blink, target["network_id"], target["id"], token(request_id)
            )
            if isinstance(response, dict) and isinstance(response.get("clips"), list):
                manifest, clips = normalize_manifest(
                    response,
                    self.adapter.namespace,
                    token(self.adapter.blink.account_id),
                    module,
                    self.camera_names(target["network_id"]),
                )
                values.update(manifest=manifest, clips=clips, request_id=None, prepared={})
                self.save(module, values)
                return values
            if attempt < 3:
                await asyncio.sleep(3 * 2**attempt)
        raise ApiError(
            503,
            "LOCAL_MANIFEST_UNAVAILABLE",
            "The module manifest did not become ready within the bounded workflow.",
            True,
        )

    async def recording_page(self, since: float, page: int) -> RecordingPage:
        async with self.serialized():
            if time.time() - self.adapter.last_inventory >= 120:
                await self.adapter.read_inventory()
            modules = list(self.adapter.local_targets)
            if not modules or len(modules) > 8:
                raise ApiError(
                    409,
                    "LOCAL_STORAGE_NOT_READY",
                    "Connect eligible, active local storage before syncing.",
                )
            # A manifest is an entire list, not the camera's latest cached clip.
            if page != 1:
                return RecordingPage([], True)
            clips: list[ClipReference] = []
            async with asyncio.timeout(180):
                for module in modules:
                    values = await self.manifest_locked(module, refresh=True)
                    for item in values["clips"]:
                        clips.append(
                            ClipReference(
                                "blink_local:" + item["key"],
                                item["camera_id"],
                                item["captured_at"],
                                item["raw_timestamp"],
                                f"local:{module}:{item['key']}",
                                False,
                            )
                        )
                    if len(clips) > 10000:
                        raise ApiError(
                            503,
                            "LOCAL_MANIFEST_LIMIT",
                            "Combined module history exceeds the safe limit. "
                            "No checkpoint was advanced.",
                        )
            return RecordingPage(clips, True)

    async def download_recording(self, media_path: str, destination: Path) -> None:
        try:
            prefix, module, clip_key = media_path.split(":")
            if prefix != "local":
                raise ValueError
            module, clip_key = str(UUID(module)), str(UUID(clip_key))
        except ValueError as exc:
            raise ApiError(
                503, "LOCAL_LOCATOR_REJECTED", "This local clip locator is unsupported."
            ) from exc
        async with self.serialized():
            values = await self.manifest_locked(module, refresh=False)
            item = next((row for row in values["clips"] if row["key"] == clip_key), None)
            if not item:
                raise ApiError(
                    410, "SOURCE_MEDIA_EXPIRED", "This clip is no longer listed by the module."
                )
            target = self.adapter.local_targets[module]
            prepared = dict(values.get("prepared", {}))
            if time.time() - float(prepared.get(clip_key, 0)) > 300:
                # Persist before posting: acceptance may precede a disconnect/restart.
                # Retry the prepared GET first instead of blindly reposting the upload.
                prepared[clip_key] = time.time()
                values["prepared"] = prepared
                self.save(module, values)
                response = await upstream_api.request_local_storage_clip(
                    self.adapter.blink,
                    target["network_id"],
                    target["id"],
                    token(values["manifest"]),
                    token(item["id"]),
                )
                if not isinstance(response, dict) or response.get("id") is None:
                    raise ApiError(
                        503,
                        "LOCAL_TRANSFER_UNAVAILABLE",
                        "The module did not prepare this clip.",
                        True,
                    )
            path = (
                "/api/v1/accounts/{}/networks/{}/sync_modules/{}"
                "/local_storage/manifest/{}/clip/request/{}"
            ).format(
                token(self.adapter.blink.account_id),
                token(target["network_id"]),
                token(target["id"]),
                token(values["manifest"]),
                token(item["id"]),
            )
            try:
                await self.adapter.download_locked(path, destination)
            except ApiError as error:
                if error.code == "SOURCE_MEDIA_EXPIRED":
                    raise ApiError(
                        503,
                        "LOCAL_TRANSFER_UNAVAILABLE",
                        "This listed clip is not ready for transfer. "
                        "Its manifest will be checked again.",
                        True,
                    ) from error
                raise
