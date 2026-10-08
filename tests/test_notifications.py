import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError
from porchlight.config import ROOT
from porchlight.notifications import (
    in_schedule,
    match_kind,
    matches,
    plan_notifications,
    validate_rule,
)
from porchlight.storage.models import (
    Analysis,
    Event,
    Job,
    MediaAsset,
    Notification,
    NotificationOutbox,
    NotificationRule,
)
from sqlalchemy import select


def rule() -> dict:
    value = json.loads((ROOT / "examples/notification-rule.example.json").read_text())
    value.update(
        camera_ids=[],
        channels=["in_app"],
        cooldown_seconds=0,
        freshness_seconds=900,
        privacy_mode="descriptive",
        categories=["vehicle"],
        colors=["white"],
        directions=[],
    )
    value["schedule"].update(
        active_iso_weekdays=[1, 2, 3, 4, 5, 6, 7],
        quiet_hours={"enabled": False, "start": "22:00", "end": "07:00"},
    )
    return dict(value)


def add_event(
    client: TestClient, recorded: datetime, *, analyzed: bool = False, historical: bool = False
) -> str:
    event_id, asset_id = str(uuid4()), str(uuid4())
    with client.app.state.db.session() as db:
        db.add(
            MediaAsset(
                id=asset_id,
                sha256=asset_id,
                relative_path=f"media/{asset_id}.mp4",
                bytes=1,
                duration_seconds=1,
                width=1,
                height=1,
            )
        )
        db.flush()
        event = Event(
            id=event_id,
            source_key=f"synthetic:{event_id}",
            source_type="blink_cloud",
            captured_at=recorded.isoformat(),
            discovered_at=datetime.now(UTC).isoformat(),
            timestamp_quality="upstream",
            media_id=asset_id,
            analysis_status="analyzed" if analyzed else "not_analyzed",
            summary="A white car is visible." if analyzed else None,
            historical=historical,
        )
        db.add(event)
        db.flush()
        if analyzed:
            job_id = str(uuid4())
            db.add(
                Job(
                    id=job_id,
                    type="ai_analyze",
                    dedup_key=job_id,
                    payload={"event_id": event_id},
                    status="done",
                    attempt=1,
                    available_at=0,
                )
            )
            db.flush()
            db.add(
                Analysis(
                    id=str(uuid4()),
                    event_id=event_id,
                    job_id=job_id,
                    revision=1,
                    model="synthetic",
                    model_digest="synthetic",
                    contract_digest="synthetic",
                    input_fingerprint="synthetic",
                    frames=[],
                    observation={
                        "entities": [
                            {"category": "vehicle", "color": "white", "direction": "unknown"}
                        ]
                    },
                    elapsed_seconds=1,
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
            db.flush()
        plan_notifications(db, event, analyzed=analyzed)
        plan_notifications(db, event, analyzed=analyzed)
        db.commit()
    return event_id


def test_recent_historical_clip_is_silent_even_after_analysis_and_rule_retry(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    assert (
        client.post(
            "/api/v1/notification-rules", headers=headers, json={"definition": rule()}
        ).status_code
        == 201
    )
    historical = add_event(client, datetime.now(UTC), analyzed=True, historical=True)
    with client.app.state.db.session() as db:
        event = db.get(Event, historical)
        plan_notifications(db, event)
        plan_notifications(db, event, analyzed=True)
        db.commit()
        assert db.scalar(select(NotificationOutbox.id)) is None
    client.app.state.notifications.dispatch()
    assert client.get("/api/v1/notifications").json()["unread"] == 0


def test_rule_matching_is_entity_scoped_and_unknown_is_conservative() -> None:
    definition = rule()
    assert not matches(
        definition,
        {
            "entities": [
                {"category": "vehicle", "color": "black"},
                {"category": "package", "color": "white"},
            ]
        },
    )
    assert matches(definition, None)
    assert matches(definition, {"entities": [{"category": "vehicle", "color": None}]})
    assert (
        match_kind(definition, {"entities": [{"category": "vehicle", "color": None}]}) == "generic"
    )
    definition["unknown_policy"] = "suppress"
    assert not matches(definition, None)


def test_quiet_hours_overnight_weekdays_and_dst() -> None:
    definition = rule()
    definition["schedule"]["quiet_hours"]["enabled"] = True
    assert not in_schedule(definition, datetime(2026, 11, 1, 5, 30, tzinfo=UTC))
    assert not in_schedule(definition, datetime(2026, 11, 1, 6, 30, tzinfo=UTC))
    assert in_schedule(definition, datetime(2026, 11, 1, 16, tzinfo=UTC))
    definition["schedule"]["active_iso_weekdays"] = [1]
    assert not in_schedule(definition, datetime(2026, 11, 1, 16, tzinfo=UTC))


def test_transactional_inbox_history_suppression_dedup_and_local_delete(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    response = client.post(
        "/api/v1/notification-rules", headers=headers, json={"definition": rule()}
    )
    assert response.status_code == 201
    old = add_event(client, datetime.now(UTC) - timedelta(days=2))
    current = add_event(client, datetime.now(UTC) - timedelta(seconds=1), analyzed=True)
    client.app.state.notifications.dispatch()
    client.app.state.notifications.dispatch()
    inbox = client.get("/api/v1/notifications").json()
    assert inbox["unread"] == 1 and len(inbox["items"]) == 1
    assert inbox["items"][0]["event_id"] == current
    assert inbox["items"][0]["body"] == "A white car is visible."
    assert (
        client.post(
            f"/api/v1/notifications/{inbox['items'][0]['id']}/read", headers=headers
        ).status_code
        == 204
    )
    assert client.get("/api/v1/notifications").json()["unread"] == 0
    assert client.delete(f"/api/v1/events/{current}", headers=headers).status_code == 204
    assert client.get("/api/v1/notifications").json()["items"] == []
    with client.app.state.db.session() as db:
        assert db.get(Event, old)
        assert not list(db.scalars(select(NotificationOutbox)))


def test_snooze_and_cooldown_preserve_recordings(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    definition = rule()
    definition["cooldown_seconds"] = 600
    client.post("/api/v1/notification-rules", headers=headers, json={"definition": definition})
    add_event(client, datetime.now(UTC) - timedelta(seconds=1))
    client.app.state.notifications.dispatch()
    add_event(client, datetime.now(UTC) - timedelta(seconds=1))
    client.app.state.notifications.dispatch()
    assert len(client.get("/api/v1/notifications").json()["items"]) == 1
    client.post("/api/v1/notifications/snooze", headers=headers, json={"minutes": 60})
    add_event(client, datetime.now(UTC) - timedelta(seconds=1))
    client.app.state.notifications.dispatch()
    assert client.get("/api/v1/notifications").json()["snoozed_until"]
    assert len(client.get("/api/v1/events").json()["items"]) == 3
    assert client.post("/api/v1/notifications/test").status_code == 403
    assert client.post("/api/v1/notifications/test", headers=headers).status_code == 201


def test_invalid_rule_rejects_actions_and_unknown_timezone() -> None:
    with pytest.raises(ApiError):
        validate_rule({**rule(), "command": "disarm"})
    value = rule()
    value["schedule"]["timezone"] = "Unknown/Zone"
    with pytest.raises(ApiError):
        validate_rule(value)


def test_rule_limit_preserves_updates_and_deletion(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    ids = [str(uuid4()) for _ in range(50)]
    with client.app.state.db.session() as db:
        db.add_all(
            [
                NotificationRule(
                    id=identifier, values=rule(), created_at=datetime.now(UTC).isoformat()
                )
                for identifier in ids
            ]
        )
        db.commit()
    response = client.post(
        "/api/v1/notification-rules", headers=headers, json={"definition": rule()}
    )
    assert response.status_code == 409 and response.json()["code"] == "RULE_LIMIT"
    changed = rule()
    changed["schedule"]["timezone"] = "America/Vancouver"
    assert (
        client.put(
            f"/api/v1/notification-rules/{ids[0]}",
            headers=headers,
            json={"definition": changed, "expected_revision": 1},
        ).status_code
        == 200
    )
    deletion = f"/api/v1/notification-rules/{ids[0]}?expected_revision=2"
    assert client.delete(deletion).status_code == 403
    assert client.delete(deletion, headers=headers).status_code == 204
    assert (
        client.post(
            "/api/v1/notification-rules", headers=headers, json={"definition": rule()}
        ).status_code
        == 201
    )
    assert len(client.get("/api/v1/notification-rules").json()) == 50


def test_inbox_cursor_handles_timestamp_ties_and_missing_anchor(authenticated) -> None:
    client, _headers = authenticated
    identifiers = [str(uuid4()) for _ in range(61)]
    with client.app.state.db.session() as db:
        db.add_all(
            [
                Notification(
                    id=identifier,
                    event_id=None,
                    rule_id=None,
                    tag=identifier,
                    title="Synthetic paging",
                    body="Synthetic inbox fixture",
                    created_at="2026-10-07T10:00:00+00:00",
                    read=False,
                )
                for identifier in identifiers
            ]
        )
        db.commit()
    seen, cursor = [], None
    for expected in (30, 30, 1):
        page = client.get(
            "/api/v1/notifications", params={"cursor": cursor} if cursor else {}
        ).json()
        assert len(page["items"]) == expected and page["unread"] == 61
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
    assert cursor is None and seen == sorted(identifiers, reverse=True)
    anchor = seen[29]
    with client.app.state.db.session() as db:
        db.delete(db.get(Notification, anchor))
        db.commit()
    assert client.get("/api/v1/notifications", params={"cursor": anchor}).status_code == 422


def test_unknown_entity_keeps_generic_alert_when_other_entities_do_not_match() -> None:
    definition = rule()
    definition["categories"], definition["colors"] = ["person"], []
    observation = {"entities": [{"category": "vehicle"}, {"category": "unknown"}]}
    assert match_kind(definition, observation) == "generic"
    definition["unknown_policy"] = "suppress"
    assert match_kind(definition, observation) is None
    definition["categories"] = ["vehicle"]
    assert match_kind(definition, observation) == "known"
