import copy
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError, PushPairRequest
from porchlight.config import Config
from porchlight.faces.descriptions import FaceDescription
from porchlight.notifications import (
    Notifications,
    plan_face_notification_update,
    plan_notifications,
)
from porchlight.operations import backup, verify
from porchlight.push import PushResult, WebPush, b64url, retry_delay, validate_endpoint
from porchlight.storage.database import Database
from porchlight.storage.models import Analysis, Event, IntegrationState, PushDelivery, PushDevice
from sqlalchemy import select
from test_notifications import add_event, rule


class Vault:
    def __init__(self) -> None:
        self.value: dict[str, Any] | None = None

    def read(self) -> dict[str, Any] | None:
        return copy.deepcopy(self.value)

    def write(self, value: dict[str, Any]) -> None:
        self.value = copy.deepcopy(value)


class Sender:
    def __init__(self) -> None:
        self.result = PushResult(201)
        self.sent: list[dict[str, Any]] = []

    def available(self) -> bool:
        return True

    def generate_keys(self) -> dict[str, str]:
        return {"public_key": b64url(b"\x04" + b"s" * 64), "private_key": "SYNTHETIC-PRIVATE-KEY"}

    def send(
        self,
        subscription: dict[str, Any],
        payload: str,
        private_key: str,
        subject: str,
        ttl: int,
        topic: str,
    ) -> PushResult:
        self.sent.append(
            {
                "subscription": subscription,
                "payload": json.loads(payload),
                "ttl": ttl,
                "topic": topic,
            }
        )
        return self.result


def pairing(
    name: str = "Synthetic phone",
    endpoint: str = "https://fcm.googleapis.com/fcm/send/synthetic_token",
) -> PushPairRequest:
    return PushPairRequest(
        name=name,
        endpoint=endpoint,
        keys={"p256dh": b64url(b"\x04" + b"k" * 64), "auth": b64url(b"a" * 16)},
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/token",
        "https://localhost/fcm/send/token",
        "https://127.0.0.1/fcm/send/token",
        "https://fcm.googleapis.com.evil.invalid/fcm/send/token",
        "https://user:password@fcm.googleapis.com/fcm/send/token",
        "https://fcm.googleapis.com:123/fcm/send/token",
        "https://fcm.googleapis.com/fcm/send/token?redirect=secret",
        "https://fcm.googleapis.com/other/token",
    ],
)
def test_push_endpoints_cannot_target_arbitrary_hosts(endpoint: str) -> None:
    with pytest.raises(ApiError):
        validate_endpoint(endpoint)


def make_push(config: Config) -> tuple[Database, WebPush, Vault, Sender]:
    db = Database(config.data_root)
    db.migrate()
    vault, sender = Vault(), Sender()
    push = WebPush(
        config.model_copy(update={"public_origin": "https://porch.example.org"}), db, vault, sender
    )
    push.configure()
    return db, push, vault, sender


def test_subscription_secrets_are_outside_sqlite_and_accepted_is_not_displayed(
    config: Config,
) -> None:
    db, push, vault, sender = make_push(config)
    try:
        result = push.pair(pairing())
        identifier = result.paired_device_id
        assert identifier
        assert push.pair(pairing()).paired_device_id == identifier
        assert len(push.status().devices) == 1
        assert (
            vault.value
            and vault.value["subscriptions"][identifier]["endpoint"] == pairing().endpoint
        )
        assert pairing().endpoint not in db.path.read_bytes().decode(errors="ignore")
        assert "SYNTHETIC-PRIVATE-KEY" not in db.path.read_bytes().decode(errors="ignore")
        push.test(identifier)
        with pytest.raises(ApiError) as error:
            push.test(identifier)
        assert error.value.code == "PUSH_TEST_WAIT"
        push.dispatch()
        push.dispatch()
        assert len(sender.sent) == 1
        payload = sender.sent[0]["payload"]
        assert set(payload) == {
            "event_id",
            "title",
            "body",
            "tag",
            "expires_at",
            "thumbnail",
            "silent",
            "update_only",
            "delivery_id",
            "issued_at",
        }
        assert payload["thumbnail"] is False and payload["update_only"] is False
        assert payload["event_id"] is None and sender.sent[0]["ttl"] <= 120
        assert len(sender.sent[0]["topic"]) <= 32
        assert push.status().deliveries[0].status == "transport_accepted"
        assert "displayed" not in push.status().model_dump_json()
        push.revoke(identifier)
        assert not push.status().devices[0].enabled
        assert identifier not in vault.value["subscriptions"]
    finally:
        db.close()


def test_retry_expiry_and_interrupted_send_are_bounded(config: Config) -> None:
    db, push, _, sender = make_push(config)
    try:
        identifier = push.pair(pairing()).paired_device_id
        assert identifier
        push.test(identifier)
        sender.result = PushResult(429, 1)
        push.dispatch()
        with db.session() as session:
            row = session.scalar(select(PushDelivery))
            assert row.status == "queued" and row.attempt == 1
            row.available_at = time.time() - 1
            session.commit()
        sender.result = PushResult(410)
        push.dispatch()
        assert push.status().deliveries[0].safe_error == "SUBSCRIPTION_EXPIRED"
        assert not push.status().devices[0].enabled
        push.pair(pairing())
        with db.session() as session:
            previous = session.scalar(select(PushDelivery))
            previous.available_at = time.time() - 31
            session.commit()
        push.test(identifier)
        sender.result = PushResult(None)
        push.dispatch()
        push.dispatch()
        assert len(sender.sent) == 3
        assert any(row.status == "delivery_unknown" for row in push.status().deliveries)
        with db.session() as session:
            row = session.scalar(
                select(PushDelivery).where(PushDelivery.status == "delivery_unknown")
            )
            row.status = "sending"
            session.commit()
        recovered = WebPush(push.config, db, push.vault, sender)
        assert any(row.safe_error == "RESTART_DURING_SEND" for row in recovered.status().deliveries)
        recovered.dispatch()
        assert len(sender.sent) == 3
    finally:
        db.close()


def test_unavailable_packages_and_local_origin_are_visible_and_protected(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    result = client.get("/api/v1/push")
    assert result.status_code == 200
    assert not result.json()["configured"] and result.json()["public_origin"] is None
    assert client.post("/api/v1/push/configure").status_code == 403
    assert client.post("/api/v1/push/configure", headers=headers).status_code == 409
    assert (
        client.post(
            "/api/v1/push/devices", headers=headers, json=pairing().model_dump()
        ).status_code
        == 409
    )
    client.cookies.clear()
    assert client.get("/api/v1/push").status_code == 401


def test_portable_backup_removes_push_pairing_and_keys(config: Config, tmp_path: Path) -> None:
    db, push, _, _ = make_push(config)
    identifier = push.pair(pairing()).paired_device_id
    assert identifier
    push.test(identifier)
    push.dispatch()
    from porchlight.api.contracts import PushReceipt

    push.receipt(
        push.status().deliveries[0].id,
        PushReceipt(
            worker_version="previews-v2",
            outcome="submitted",
            preview="not_requested",
            descriptive=False,
        ),
    )
    db.close()
    # A normal app supplies settings/scan tables even before camera setup.
    with TestClient(__import__("porchlight.app", fromlist=["create_app"]).create_app(config)):
        pass
    destination = tmp_path / "push-safe-backup"
    assert backup(config, destination)["passed"]
    assert verify(destination)
    copy_db = Database(destination)
    try:
        with copy_db.session() as session:
            assert list(session.scalars(select(PushDevice))) == []
            assert list(session.scalars(select(PushDelivery))) == []
            assert session.get(IntegrationState, "push_control") is None
            assert (
                list(
                    session.scalars(
                        select(IntegrationState).where(IntegrationState.id.like("push_receipt:%"))
                    )
                )
                == []
            )
    finally:
        copy_db.close()


def test_provider_retry_after_is_bounded() -> None:
    assert retry_delay("99999999") == 3600
    assert retry_delay("0") == 1
    assert retry_delay("invalid") == 30
    assert retry_delay(datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")) == 1


def test_rule_fanout_is_per_device_idempotent_and_respects_snooze(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = authenticated
    db = client.app.state.db
    sender, vault = Sender(), Vault()
    push = WebPush(
        client.app.state.config.model_copy(update={"public_origin": "https://porch.example.org"}),
        db,
        vault,
        sender,
    )
    push.configure()
    first = push.pair(pairing()).paired_device_id
    second = push.pair(
        pairing(
            "Second synthetic phone",
            "https://updates.push.services.mozilla.com/wpush/v2/second_token",
        )
    ).paired_device_id
    notifications = Notifications(db, push)
    definition = rule()
    definition.update(enabled=True, channels=["web_push"], privacy_mode="generic")
    notifications.save_rule(definition)
    event_id = add_event(client, datetime.now(UTC))
    notifications.dispatch()
    notifications.dispatch()
    with db.session() as session:
        deliveries = list(session.scalars(select(PushDelivery)))
        assert len(deliveries) == 2 and {row.device_id for row in deliveries} == {first, second}
    push.dispatch()
    push.dispatch()
    push.dispatch()
    assert len(sender.sent) == 2
    assert all(message["payload"]["event_id"] == event_id for message in sender.sent)
    assert all(
        message["payload"]["body"]
        == "New camera activity. Open Porchlight to review the recording."
        for message in sender.sent
    )
    assert sender.sent[0]["topic"] == sender.sent[1]["topic"]
    notifications.snooze(60)
    add_event(client, datetime.now(UTC))
    notifications.dispatch()
    push.dispatch()
    assert len(sender.sent) == 2


def test_rule_changed_after_fanout_and_deleted_event_cannot_send(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    db = client.app.state.db
    sender, vault = Sender(), Vault()
    push = WebPush(
        client.app.state.config.model_copy(update={"public_origin": "https://porch.example.org"}),
        db,
        vault,
        sender,
    )
    push.configure()
    push.pair(pairing())
    notifications = Notifications(db, push)
    definition = rule()
    definition.update(enabled=True, channels=["web_push"])
    saved = notifications.save_rule(definition)
    event = add_event(client, datetime.now(UTC))
    notifications.dispatch()
    definition["enabled"] = False
    saved = notifications.save_rule(definition, saved.id, saved.revision)
    push.dispatch()
    assert sender.sent == [] and push.status().deliveries[0].status == "expired"
    definition["enabled"] = True
    notifications.save_rule(definition, saved.id, saved.revision)
    second = add_event(client, datetime.now(UTC))
    notifications.dispatch()
    assert client.delete(f"/api/v1/events/{second}", headers=headers).status_code == 204
    push.dispatch()
    assert sender.sent == []
    assert client.get(f"/api/v1/events/{event}").status_code == 200


def test_descriptive_push_updates_the_same_recording_without_replaying_history(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = authenticated
    db = client.app.state.db
    sender = Sender()
    push = WebPush(
        client.app.state.config.model_copy(update={"public_origin": "https://porch.example.org"}),
        db,
        Vault(),
        sender,
    )
    push.configure()
    push.pair(pairing())
    notifications = Notifications(db, push)
    definition = rule()
    definition.update(enabled=True, channels=["in_app", "web_push"], privacy_mode="descriptive")
    notifications.save_rule(definition)
    event_id = add_event(client, datetime.now(UTC))
    notifications.dispatch()
    push.dispatch()
    assert len(sender.sent) == 1
    assert sender.sent[0]["payload"]["body"].startswith("New camera activity.")

    # Reuse a synthetic historical analysis as the completed local AI result.
    # The historical event itself must stay silent.
    template_id = add_event(client, datetime.now(UTC), analyzed=True, historical=True)
    with db.session() as session:
        template = session.scalar(select(Analysis).where(Analysis.event_id == template_id))
        event = session.get(Event, event_id)
        assert template and event
        template.event_id = event_id
        event.summary, event.analysis_status = "A white car is visible.", "analyzed"
        session.flush()
        plan_notifications(session, event, analyzed=True)
        plan_notifications(session, event, analyzed=True)
        session.commit()
    notifications.dispatch()
    push.dispatch()
    notifications.dispatch()
    push.dispatch()
    assert len(sender.sent) == 2
    first, updated = [message["payload"] for message in sender.sent]
    assert updated["body"] == "A white car is visible."
    assert first["event_id"] == updated["event_id"] == event_id
    assert first["tag"] == updated["tag"]
    assert sender.sent[0]["topic"] == sender.sent[1]["topic"]
    inbox = notifications.inbox()
    assert len(inbox.items) == 1 and inbox.items[0].body == updated["body"]


def test_face_completion_updates_same_alert_once_and_preserves_unknowns(authenticated):
    client, _ = authenticated
    db = client.app.state.db
    sender = Sender()
    push = WebPush(
        client.app.state.config.model_copy(update={"public_origin": "https://porch.example.org"}),
        db,
        Vault(),
        sender,
    )
    push.configure()
    push.pair(pairing())
    contexts: dict[str, FaceDescription] = {}
    notifications = Notifications(db, push, lambda _: contexts)
    definition = rule()
    definition.update(
        enabled=True,
        channels=["in_app", "web_push"],
        categories=[],
        colors=[],
        include_thumbnail=True,
    )
    notifications.save_rule(definition)
    event_id = add_event(client, datetime.now(UTC), analyzed=True)
    with db.session() as session:
        event = session.get(Event, event_id)
        assert event
        event.summary = "A person approaches. A car is visible."
        session.commit()
    notifications.dispatch()
    push.dispatch()
    assert sender.sent[-1]["payload"]["body"].startswith("A person")
    assert sender.sent[-1]["payload"]["thumbnail"] is True
    contexts[event_id] = FaceDescription(("Alex",), "Alex")
    with db.session() as session:
        event = session.get(Event, event_id)
        assert event
        plan_face_notification_update(session, event)
        session.flush()
        plan_face_notification_update(session, event)
        session.commit()
    notifications.dispatch()
    push.dispatch()
    notifications.dispatch()
    push.dispatch()
    assert len(sender.sent) == 2
    first, updated = [item["payload"] for item in sender.sent]
    assert updated["body"] == "Alex approaches. A car is visible."
    assert updated["silent"] is True and updated["update_only"] is True
    assert first["tag"] == updated["tag"] and first["event_id"] == updated["event_id"]
    assert sender.sent[0]["topic"] == sender.sent[1]["topic"]
    assert len(notifications.inbox().items) == 1
    assert notifications.inbox().items[0].body == updated["body"]


def test_notification_thumbnail_is_authenticated_no_store_and_deleted_clip_fails(
    authenticated,
    synthetic_mp4,
):
    client, headers = authenticated
    response = client.post(
        "/api/v1/imports", content=synthetic_mp4, headers={**headers, "Content-Type": "video/mp4"}
    )
    assert response.status_code == 201
    event_id = response.json()["id"]
    target = f"/api/v1/events/{event_id}/notification-thumbnail"
    image = client.get(target)
    assert image.status_code == 200 and image.content.startswith(b"\xff\xd8")
    assert image.headers["cache-control"] == "no-store"
    assert len(image.content) <= 512 * 1024
    assert client.get(target, headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert client.delete(f"/api/v1/events/{event_id}", headers=headers).status_code == 204
    assert client.get(target).status_code == 404
    client.cookies.clear()
    assert client.get(target).status_code == 401


def test_phone_receipt_requires_session_csrf_and_bounded_metadata(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    from uuid import uuid4

    client, headers = authenticated
    device_id, delivery_id = str(uuid4()), str(uuid4())
    now = datetime.now(UTC).isoformat()
    with client.app.state.db.session() as session:
        session.add(
            PushDevice(
                id=device_id,
                name="Synthetic phone",
                endpoint_hash="synthetic",
                enabled=True,
                created_at=now,
            )
        )
        session.flush()
        session.add(
            PushDelivery(
                id=delivery_id,
                device_id=device_id,
                outbox_id=None,
                event_id=None,
                dedup_key="synthetic-receipt",
                tag="synthetic",
                body="Synthetic alert",
                status="transport_accepted",
                created_at=now,
                available_at=time.time(),
                expires_at=time.time() + 120,
                attempt=1,
                safe_error=None,
            )
        )
        session.commit()
    target = f"/api/v1/push/deliveries/{delivery_id}/receipt"
    body = {
        "worker_version": "previews-v2",
        "outcome": "submitted",
        "preview": "ready",
        "descriptive": True,
    }
    assert client.post(target, json=body).status_code == 403
    assert (
        client.post(
            target, headers=headers, json={**body, "body": "must not store text"}
        ).status_code
        == 422
    )
    assert client.post(target, headers=headers, json=body).status_code == 204
    assert client.post(target, headers=headers, json=body).status_code == 204
    delivery = client.get("/api/v1/push").json()["deliveries"][0]
    assert delivery["browser_receipt"] == body
    assert delivery["status"] == "transport_accepted"  # Does not claim OS display.
    assert (
        client.post(
            f"/api/v1/push/deliveries/{uuid4()}/receipt", headers=headers, json=body
        ).status_code
        == 404
    )
    client.cookies.clear()
    assert client.post(target, headers=headers, json=body).status_code == 401


def test_notification_and_push_workers_wake_immediately_without_waiting_for_fallback(
    config: Config,
) -> None:
    import asyncio
    from unittest.mock import Mock

    async def run() -> None:
        db, push, _, _ = make_push(config)
        notifications = Notifications(db, push)
        notifications.dispatch = Mock()  # type: ignore[method-assign]
        push.dispatch = Mock()  # type: ignore[method-assign]
        tasks = [asyncio.create_task(notifications.run()), asyncio.create_task(push.run())]
        try:

            async def tick() -> None:
                while notifications.dispatch.call_count < 1 or push.dispatch.call_count < 1:
                    await asyncio.sleep(0.001)

            await asyncio.wait_for(tick(), 0.5)
            notifications.dispatch.reset_mock()
            push.dispatch.reset_mock()
            notifications.notify_work()
            await asyncio.wait_for(tick(), 0.5)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            db.close()

    asyncio.run(run())
