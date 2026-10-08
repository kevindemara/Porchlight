"""Optional Web Push. Encrypted device secrets, bounded delivery, no private media payloads."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib
import importlib.util
import ipaddress
import json
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from porchlight.api.contracts import (
    ApiError,
    PushDeliveryView,
    PushDeviceView,
    PushPairRequest,
    PushStatus,
)
from porchlight.config import Config
from porchlight.security.vault import SecretStore
from porchlight.storage.database import Database
from porchlight.storage.models import (
    IntegrationState,
    NotificationOutbox,
    NotificationRule,
    PushDelivery,
    PushDevice,
)
from porchlight.storage.work import local_work


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def decode_key(value: str, length: int) -> bytes:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+={0,2}", value):
        raise ApiError(422, "INVALID_SUBSCRIPTION", "The browser subscription is invalid.")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        if len(raw) != length:
            raise ValueError("Wrong length")
        return raw
    except ValueError as error:
        raise ApiError(
            422, "INVALID_SUBSCRIPTION", "The browser subscription is invalid."
        ) from error


def validate_endpoint(endpoint: str) -> None:
    try:
        url = urlsplit(endpoint)
        allowed = {
            "fcm.googleapis.com": r"/fcm/send/[a-zA-Z0-9_:\-]+",
            "updates.push.services.mozilla.com": r"/wpush/v[12]/[a-zA-Z0-9_\-]+",
        }
        if (
            url.scheme != "https"
            or url.port not in {None, 443}
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.hostname not in allowed
            or not re.fullmatch(allowed[url.hostname], url.path)
        ):
            raise ValueError("Unsupported endpoint")
    except ValueError as error:
        raise ApiError(
            422, "UNSUPPORTED_PUSH_PROVIDER", "Use Chrome or Firefox with a supported push service."
        ) from error


def retry_delay(value: str | None) -> float:
    try:
        delay = (
            float(value or "30")
            if (value or "30").isdigit()
            else (parsedate_to_datetime(str(value)).timestamp() - time.time())
        )
        return max(1, min(delay, 3600))
    except (ValueError, TypeError, OverflowError):
        return 30


@dataclass(frozen=True)
class PushResult:
    status: int | None
    retry_after: float = 30


class PushSender(Protocol):
    def available(self) -> bool: ...
    def generate_keys(self) -> dict[str, str]: ...
    def send(
        self,
        subscription: dict[str, Any],
        payload: str,
        private_key: str,
        subject: str,
        ttl: int,
        topic: str,
    ) -> PushResult: ...


class SafePushSession:
    """pywebpush's HTTP seam uses our bounded, redirect-free client."""

    def post(self, url: str, timeout: float | None = None, **values: Any) -> httpx.Response:
        validate_endpoint(url)
        hostname = str(urlsplit(url).hostname)
        resolved = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        if not resolved or any(
            not ipaddress.ip_address(record[4][0]).is_global for record in resolved
        ):
            raise ValueError("Push service must resolve to public addresses")
        # Library URL logging includes opaque endpoint secrets; suppress it in this process.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        if isinstance(values.get("data"), bytes):
            values["content"] = values.pop("data")
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            with client.stream("POST", url, **values) as response:
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 4096:
                        raise ValueError("Oversized push response")
                return httpx.Response(
                    response.status_code,
                    headers=response.headers,
                    content=bytes(body),
                    request=response.request,
                )


class NativePushSender:
    def available(self) -> bool:
        return all(
            importlib.util.find_spec(name) is not None
            for name in ("pywebpush", "cryptography", "py_vapid", "http_ece")
        )

    def generate_keys(self) -> dict[str, str]:
        ec = importlib.import_module("cryptography.hazmat.primitives.asymmetric.ec")
        serialization = importlib.import_module("cryptography.hazmat.primitives.serialization")
        key = ec.generate_private_key(ec.SECP256R1())
        private = key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public = key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        return {"private_key": base64.b64encode(private).decode(), "public_key": b64url(public)}

    def send(
        self,
        subscription: dict[str, Any],
        payload: str,
        private_key: str,
        subject: str,
        ttl: int,
        topic: str,
    ) -> PushResult:
        library = importlib.import_module("pywebpush")
        try:
            result = library.webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                content_encoding="aes128gcm",
                ttl=ttl,
                timeout=10,
                headers={"Topic": topic, "Urgency": "normal"},
                requests_session=SafePushSession(),
                verbose=False,
            )
            return PushResult(
                int(result.status_code), retry_delay(result.headers.get("Retry-After"))
            )
        except library.WebPushException as error:
            return PushResult(error.status_code, retry_delay(error.retry_after))
        except Exception:
            # An ambiguous failure may follow acceptance. Do not blindly resend it.
            return PushResult(None)


class WebPush:
    def __init__(
        self, config: Config, db: Database, vault: SecretStore, sender: PushSender | None = None
    ):
        self.config, self.db, self.vault = config, db, vault
        self.sender = sender or NativePushSender()
        self.lock = threading.RLock()
        with db.session() as session:
            for delivery in session.scalars(
                select(PushDelivery).where(PushDelivery.status == "sending")
            ):
                delivery.status, delivery.safe_error = "delivery_unknown", "RESTART_DURING_SEND"
            session.commit()

    def status(self) -> PushStatus:
        with self.db.session() as session:
            control = session.get(IntegrationState, "push_control")
            configured = bool(
                control
                and control.values.get("origin") == self.config.public_origin
                and self.config.public_origin
            )
            available = self.sender.available()
            return PushStatus(
                dependency_ready=available,
                configured=configured,
                public_origin=self.config.public_origin,
                public_key=control.values["public_key"] if configured and control else None,
                message=(
                    "Install the optional Web Push packages before setup."
                    if not available
                    else "Configure a stable HTTPS origin before phone setup."
                    if not self.config.public_origin
                    else "Create local push keys before pairing a browser."
                    if not configured
                    else "Pair a browser and test its locked-screen delivery. "
                    "Acceptance is not proof of display."
                ),
                devices=[
                    PushDeviceView(
                        id=row.id, name=row.name, enabled=row.enabled, created_at=row.created_at
                    )
                    for row in session.scalars(select(PushDevice).order_by(PushDevice.created_at))
                ],
                deliveries=[
                    PushDeliveryView(
                        id=row.id,
                        device_id=row.device_id,
                        event_id=row.event_id,
                        status=row.status,
                        created_at=row.created_at,
                        safe_error=row.safe_error,
                    )
                    for row in session.scalars(
                        select(PushDelivery).order_by(PushDelivery.created_at.desc()).limit(30)
                    )
                ],
            )

    def configure(self) -> PushStatus:
        if not self.sender.available():
            raise ApiError(
                409, "PUSH_PACKAGES_REQUIRED", "Install the optional Web Push packages first."
            )
        if not self.config.public_origin:
            raise ApiError(409, "HTTPS_ORIGIN_REQUIRED", "Configure a stable HTTPS origin first.")
        with self.lock, self.db.session() as session:
            control = session.get(IntegrationState, "push_control")
            if control and control.values.get("origin") == self.config.public_origin:
                return self.status()
            if session.scalar(
                select(func.count()).select_from(PushDevice).where(PushDevice.enabled)
            ):
                raise ApiError(
                    409, "PUSH_DEVICES_ACTIVE", "Revoke paired browsers before changing the origin."
                )
            keys = self.sender.generate_keys()
            self.vault.write({**keys, "origin": self.config.public_origin, "subscriptions": {}})
            if not control:
                control = IntegrationState(id="push_control", values={})
                session.add(control)
            control.values = {"origin": self.config.public_origin, "public_key": keys["public_key"]}
            session.commit()
        return self.status()

    def pair(self, value: PushPairRequest) -> PushStatus:
        if not self.sender.available():
            raise ApiError(
                409, "PUSH_PACKAGES_REQUIRED", "Install the optional Web Push packages first."
            )
        validate_endpoint(value.endpoint)
        if decode_key(value.keys.p256dh, 65)[0] != 4:
            raise ApiError(422, "INVALID_SUBSCRIPTION", "The browser encryption key is invalid.")
        decode_key(value.keys.auth, 16)
        if isinstance(self.sender, NativePushSender):
            ec = importlib.import_module("cryptography.hazmat.primitives.asymmetric.ec")
            try:
                ec.EllipticCurvePublicKey.from_encoded_point(
                    ec.SECP256R1(), decode_key(value.keys.p256dh, 65)
                )
            except ValueError as error:
                raise ApiError(
                    422, "INVALID_SUBSCRIPTION", "The browser encryption key is invalid."
                ) from error
        name = value.name.strip()
        if not name or any(ord(c) < 32 for c in name):
            raise ApiError(422, "INVALID_DEVICE_NAME", "Give this browser a short name.")
        with self.lock, self.db.session() as session:
            secrets = self.vault.read()
            if (
                not secrets
                or secrets.get("origin") != self.config.public_origin
                or not self.config.public_origin
            ):
                raise ApiError(409, "PUSH_NOT_CONFIGURED", "Set up local push keys first.")
            endpoint_hash = hashlib.sha256(value.endpoint.encode()).hexdigest()
            device = session.scalar(
                select(PushDevice).where(PushDevice.endpoint_hash == endpoint_hash)
            )
            if not device:
                if (
                    session.scalar(
                        select(func.count()).select_from(PushDevice).where(PushDevice.enabled)
                    )
                    or 0
                ) >= 8:
                    raise ApiError(
                        409, "PUSH_DEVICE_LIMIT", "Revoke an unused browser before pairing another."
                    )
                device = PushDevice(
                    id=str(uuid4()),
                    endpoint_hash=endpoint_hash,
                    name=name,
                    enabled=True,
                    created_at=datetime.now(UTC).isoformat(),
                )
                session.add(device)
            device.name, device.enabled = name, True
            subscriptions = dict(secrets.get("subscriptions", {}))
            subscriptions[device.id] = {"endpoint": value.endpoint, "keys": value.keys.model_dump()}
            self.vault.write({**secrets, "subscriptions": subscriptions})
            session.commit()
        return self.status().model_copy(update={"paired_device_id": device.id})

    def revoke(self, identifier: str) -> None:
        with self.lock, self.db.session() as session:
            device = session.get(PushDevice, identifier)
            if not device:
                raise ApiError(404, "PUSH_DEVICE_NOT_FOUND", "This paired browser is unavailable.")
            secrets = self.vault.read()
            if secrets:
                subscriptions = dict(secrets.get("subscriptions", {}))
                subscriptions.pop(identifier, None)
                self.vault.write({**secrets, "subscriptions": subscriptions})
            device.enabled = False
            for delivery in session.scalars(
                select(PushDelivery).where(
                    PushDelivery.device_id == identifier, PushDelivery.status == "queued"
                )
            ):
                delivery.status = "expired"
            session.commit()

    def test(self, identifier: str) -> PushStatus:
        with self.db.session() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            device = session.get(PushDevice, identifier)
            if not device or not device.enabled:
                raise ApiError(404, "PUSH_DEVICE_NOT_FOUND", "Pair this browser first.")
            last = session.scalar(
                select(PushDelivery.available_at)
                .where(PushDelivery.device_id == identifier, PushDelivery.outbox_id.is_(None))
                .order_by(PushDelivery.available_at.desc())
                .limit(1)
            )
            if last and time.time() - last < 30:
                raise ApiError(
                    429, "PUSH_TEST_WAIT", "Wait 30 seconds between push tests.", retry_after=30
                )
            now = time.time()
            identifier = str(uuid4())
            session.add(
                PushDelivery(
                    id=identifier,
                    device_id=device.id,
                    outbox_id=None,
                    event_id=None,
                    dedup_key=f"test:{identifier}",
                    tag="porchlight-test",
                    body="Porchlight test. Check that the alert appears with the screen locked.",
                    status="queued",
                    created_at=datetime.now(UTC).isoformat(),
                    available_at=now,
                    expires_at=now + 120,
                    attempt=0,
                )
            )
            session.commit()
        return self.status()

    @staticmethod
    def fanout(session: Session, item: NotificationOutbox, body: str) -> None:
        rule = session.get(NotificationRule, item.rule_id)
        assert rule
        tag = f"{item.event_id}:{item.rule_id}"
        last = session.scalar(
            select(PushDelivery.created_at)
            .join(NotificationOutbox, PushDelivery.outbox_id == NotificationOutbox.id)
            .where(
                NotificationOutbox.rule_id == item.rule_id,
                PushDelivery.tag != tag,
                PushDelivery.status.in_(["queued", "sending", "transport_accepted"]),
            )
            .order_by(PushDelivery.created_at.desc())
            .limit(1)
        )
        if (
            last
            and (datetime.now(UTC) - datetime.fromisoformat(last)).total_seconds()
            < rule.values["cooldown_seconds"]
        ):
            item.status = "expired"
            return
        devices = list(session.scalars(select(PushDevice).where(PushDevice.enabled)))
        for device in devices:
            dedup = f"{item.id}:{device.id}"
            if not session.scalar(select(PushDelivery.id).where(PushDelivery.dedup_key == dedup)):
                session.add(
                    PushDelivery(
                        id=str(uuid4()),
                        device_id=device.id,
                        outbox_id=item.id,
                        event_id=item.event_id,
                        dedup_key=dedup,
                        tag=tag,
                        body=body,
                        status="queued",
                        created_at=datetime.now(UTC).isoformat(),
                        available_at=time.time(),
                        expires_at=item.expires_at,
                        attempt=0,
                    )
                )
        item.status, item.safe_error = (
            ("fanout_queued", None) if devices else ("blocked", "NO_PAIRED_BROWSER")
        )

    def dispatch(self) -> None:
        from porchlight.notifications import in_schedule

        if not self.sender.available() or not self.config.public_origin:
            return
        with self.lock:
            secrets = self.vault.read()
            if not secrets or secrets.get("origin") != self.config.public_origin:
                return
            with self.db.session() as session:
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                delivery = session.scalar(
                    select(PushDelivery)
                    .where(
                        PushDelivery.status == "queued", PushDelivery.available_at <= time.time()
                    )
                    .order_by(PushDelivery.available_at)
                    .limit(1)
                )
                if not delivery:
                    return
                device = session.get(PushDevice, delivery.device_id)
                parent = (
                    session.get(NotificationOutbox, delivery.outbox_id)
                    if delivery.outbox_id
                    else None
                )
                rule = session.get(NotificationRule, parent.rule_id) if parent else None
                control = session.get(IntegrationState, "notification_control")
                subscription = secrets.get("subscriptions", {}).get(delivery.device_id)
                if (
                    not device
                    or not device.enabled
                    or not subscription
                    or delivery.expires_at <= time.time()
                    or delivery.outbox_id
                    and (
                        not rule
                        or not rule.values["enabled"]
                        or not in_schedule(rule.values, datetime.now(UTC))
                        or control
                        and control.values.get("snoozed_until", 0) > time.time()
                    )
                ):
                    delivery.status = "expired"
                    session.commit()
                    return
                delivery.status, delivery.attempt = "sending", delivery.attempt + 1
                session.commit()
            payload = json.dumps(
                {
                    "event_id": delivery.event_id,
                    "title": "Porchlight activity" if delivery.event_id else "Porchlight test",
                    "body": delivery.body[:500],
                    "tag": delivery.tag,
                    "expires_at": delivery.expires_at,
                },
                separators=(",", ":"),
            )
            ttl = max(1, min(900, int(delivery.expires_at - time.time())))
            try:
                result = self.sender.send(
                    subscription,
                    payload,
                    secrets["private_key"],
                    self.config.public_origin,
                    ttl,
                    b64url(hashlib.sha256(delivery.tag.encode()).digest()[:16]),
                )
            except Exception:
                result = PushResult(None)
            if result.status in {404, 410}:
                self.revoke(delivery.device_id)
            with self.db.session() as session:
                saved = session.get(PushDelivery, delivery.id)
                if not saved:
                    return
                if result.status is not None and 200 <= result.status < 300:
                    saved.status, saved.safe_error = "transport_accepted", None
                elif result.status in {404, 410}:
                    saved.status, saved.safe_error = "expired", "SUBSCRIPTION_EXPIRED"
                elif (
                    result.status in {429, 500, 502, 503, 504}
                    and saved.attempt < 5
                    and time.time() + result.retry_after < saved.expires_at
                ):
                    saved.status, saved.safe_error = "queued", "PUSH_PROVIDER_RETRY"
                    saved.available_at = time.time() + max(
                        result.retry_after, min(300, 15 * 2**saved.attempt)
                    )
                else:
                    saved.status = "delivery_unknown" if result.status is None else "failed"
                    saved.safe_error = (
                        "PUSH_DELIVERY_UNKNOWN"
                        if result.status is None
                        else "PUSH_PROVIDER_REJECTED"
                    )
                session.commit()

    async def run(self) -> None:
        while True:
            self.last_tick = time.time()
            try:
                await local_work(self.dispatch)
            except Exception:
                logging.getLogger("porchlight").error('{"event":"push_worker_retry"}')
            await asyncio.sleep(2)
