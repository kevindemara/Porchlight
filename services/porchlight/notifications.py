from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from porchlight.api.contracts import ApiError, InboxItem, InboxView, RuleView
from porchlight.config import ROOT
from porchlight.faces.descriptions import FaceDescription, personalize_summary
from porchlight.push import WebPush
from porchlight.storage.database import Database
from porchlight.storage.models import (
    Analysis,
    Event,
    IntegrationState,
    Notification,
    NotificationOutbox,
    NotificationRule,
)
from porchlight.storage.work import local_work

RULE_SCHEMA = json.loads(
    (ROOT / "schemas/notification-rule.schema.json").read_text(encoding="utf-8")
)


def validate_rule(value: dict[str, Any]) -> dict[str, Any]:
    try:
        Draft202012Validator(RULE_SCHEMA, format_checker=FormatChecker()).validate(value)
        ZoneInfo(value["schedule"]["timezone"])
        return value
    except (ValidationError, ValueError, KeyError) as exc:
        raise ApiError(422, "INVALID_RULE", "Review the rule's filters and schedule.") from exc


def in_schedule(rule: dict[str, Any], now: datetime) -> bool:
    local = now.astimezone(ZoneInfo(rule["schedule"]["timezone"]))
    schedule = rule["schedule"]
    if local.isoweekday() not in schedule["active_iso_weekdays"]:
        return False
    quiet = schedule["quiet_hours"]
    clock = local.strftime("%H:%M")
    start, end = quiet["start"], quiet["end"]
    if quiet["enabled"] and (
        start <= clock < end if start < end else clock >= start or clock < end
    ):
        return False
    return True


def match_kind(rule: dict[str, Any], observation: dict[str, Any] | None) -> str | None:
    entities = observation.get("entities", []) if observation else []
    known = [entity for entity in entities if entity["category"] != "unknown"]
    if not known:
        return "generic" if rule["unknown_policy"] == "notify_generic" else None
    uncertain = any(entity["category"] == "unknown" for entity in entities)
    for entity in known:
        if rule["categories"] and entity["category"] not in rule["categories"]:
            continue
        uncertain_color = bool(rule["colors"]) and entity.get("color") is None
        uncertain_direction = bool(rule["directions"]) and entity.get("direction") in {
            None,
            "unknown",
        }
        if (uncertain_color or uncertain_direction) and rule["unknown_policy"] == "notify_generic":
            uncertain = True
            continue
        if (not rule["colors"] or entity.get("color") in rule["colors"]) and (
            not rule["directions"] or entity.get("direction") in rule["directions"]
        ):
            return "known"
    return "generic" if uncertain and rule["unknown_policy"] == "notify_generic" else None


def matches(rule: dict[str, Any], observation: dict[str, Any] | None) -> bool:
    return match_kind(rule, observation) is not None


def plan_notifications(db: Session, event: Event, *, analyzed: bool = False) -> None:
    """Called inside the event/analysis transaction. Reanalysis and history are silent."""
    if (
        event.historical
        or event.source_type not in {"blink_cloud", "blink_local"}
        or not event.captured_at
    ):
        return
    now = datetime.now(UTC)
    recorded = datetime.fromisoformat(event.captured_at)
    observation = (
        db.scalar(
            select(Analysis.observation)
            .where(Analysis.event_id == event.id)
            .order_by(Analysis.revision.desc())
            .limit(1)
        )
        if analyzed
        else None
    )
    for row in db.scalars(select(NotificationRule)):
        rule = row.values
        if (
            not rule["enabled"]
            or event.discovered_at < row.created_at
            or not 0 <= (now - recorded).total_seconds() <= rule["freshness_seconds"]
            or (rule["camera_ids"] and event.camera_id not in rule["camera_ids"])
        ):
            continue
        if not matches(rule, observation):
            continue
        for channel in rule["channels"]:
            key = f"{event.id}:{row.id}:{channel}:{'analysis' if analyzed else 'initial'}"
            if not db.scalar(
                select(NotificationOutbox.id).where(NotificationOutbox.dedup_key == key)
            ):
                db.add(
                    NotificationOutbox(
                        id=str(uuid4()),
                        event_id=event.id,
                        rule_id=row.id,
                        channel=channel,
                        kind="analysis" if analyzed else "initial",
                        dedup_key=key,
                        status="queued",
                        available_at=time.time(),
                        expires_at=recorded.timestamp() + rule["freshness_seconds"],
                        attempt=0,
                    )
                )


def plan_face_notification_update(db: Session, event: Event) -> None:
    """Refresh only already-dispatched descriptive alerts, never create a new alert."""
    if event.historical or event.analysis_status != "analyzed":
        return
    for prior in db.scalars(
        select(NotificationOutbox).where(
            NotificationOutbox.event_id == event.id,
            NotificationOutbox.kind == "analysis",
            NotificationOutbox.status.in_(["transport_accepted", "fanout_queued"]),
            NotificationOutbox.expires_at > time.time(),
        )
    ):
        rule = db.get(NotificationRule, prior.rule_id)
        key = f"{event.id}:{prior.rule_id}:{prior.channel}:faces"
        if (
            not rule
            or not rule.values["enabled"]
            or rule.values["privacy_mode"] != "descriptive"
            or db.scalar(select(NotificationOutbox.id).where(NotificationOutbox.dedup_key == key))
        ):
            continue
        db.add(
            NotificationOutbox(
                id=str(uuid4()),
                event_id=event.id,
                rule_id=prior.rule_id,
                channel=prior.channel,
                kind="faces",
                dedup_key=key,
                status="queued",
                available_at=time.time(),
                expires_at=prior.expires_at,
                attempt=0,
            )
        )


class Notifications:
    def __init__(
        self,
        db: Database,
        push: WebPush | None = None,
        face_contexts: Callable[[list[str]], dict[str, FaceDescription]] | None = None,
    ):
        self.db, self.push = db, push
        self.face_contexts = face_contexts
        self.wake = asyncio.Event()

    def rules(self) -> list[RuleView]:
        with self.db.session() as db:
            return [
                RuleView(
                    id=row.id,
                    created_at=row.created_at,
                    definition=row.values,
                    revision=row.revision,
                )
                for row in db.scalars(
                    select(NotificationRule).order_by(NotificationRule.created_at)
                )
            ]

    def save_rule(
        self,
        value: dict[str, Any],
        identifier: str | None = None,
        expected_revision: int | None = None,
    ) -> RuleView:
        value = validate_rule(value)
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            if identifier:
                row = db.get(NotificationRule, identifier)
                if not row:
                    raise ApiError(404, "RULE_NOT_FOUND", "This rule is unavailable.")
                self.require_revision(row, expected_revision)
                row.revision += 1
            else:
                count = db.scalar(select(func.count()).select_from(NotificationRule)) or 0
                if count >= 50:
                    raise ApiError(409, "RULE_LIMIT", "Keep at most 50 notification rules.")
                row = NotificationRule(
                    id=str(uuid4()), values=value, created_at=datetime.now(UTC).isoformat()
                )
                db.add(row)
            row.values = value
            db.commit()
            return RuleView(
                id=row.id, created_at=row.created_at, definition=row.values, revision=row.revision
            )

    @staticmethod
    def require_revision(row: NotificationRule, expected_revision: int | None) -> None:
        if expected_revision is None:
            raise ApiError(409, "RULE_VERSION_REQUIRED", "Reload the rule before changing it.")
        if expected_revision != row.revision:
            raise ApiError(
                409,
                "RULE_CONFLICT",
                "This rule changed in another browser. Reload its saved version before continuing.",
            )

    def delete_rule(self, identifier: str, expected_revision: int) -> None:
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            row = db.get(NotificationRule, identifier)
            if not row:
                raise ApiError(404, "RULE_NOT_FOUND", "This rule is unavailable.")
            self.require_revision(row, expected_revision)
            db.delete(row)
            db.commit()

    def snooze(self, minutes: int) -> None:
        with self.db.session() as db:
            row = db.get(IntegrationState, "notification_control")
            if not row:
                row = IntegrationState(id="notification_control", values={})
                db.add(row)
            row.values = {"snoozed_until": time.time() + minutes * 60 if minutes else 0}
            db.commit()

    def inbox(self, cursor: str | None = None) -> InboxView:
        with self.db.session() as db:
            query = select(Notification)
            if cursor:
                previous = db.get(Notification, cursor)
                if not previous:
                    raise ApiError(422, "INVALID_CURSOR", "Refresh notifications.")
                query = query.where(
                    (Notification.created_at < previous.created_at)
                    | (
                        (Notification.created_at == previous.created_at)
                        & (Notification.id < previous.id)
                    )
                )
            rows = list(
                db.scalars(
                    query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(31)
                )
            )
            control = db.get(IntegrationState, "notification_control")
            until = control.values.get("snoozed_until", 0) if control else 0
            return InboxView(
                items=[
                    InboxItem(
                        id=row.id,
                        event_id=row.event_id,
                        title=row.title,
                        body=row.body,
                        created_at=row.created_at,
                        read=row.read,
                    )
                    for row in rows[:30]
                ],
                unread=int(
                    db.scalar(
                        select(func.count())
                        .select_from(Notification)
                        .where(Notification.read.is_(False))
                    )
                    or 0
                ),
                next_cursor=rows[29].id if len(rows) > 30 else None,
                snoozed_until=datetime.fromtimestamp(until, UTC).isoformat()
                if until > time.time()
                else None,
            )

    def dispatch(self) -> None:
        now = datetime.now(UTC)
        with self.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            control = db.get(IntegrationState, "notification_control")
            snoozed = control.values.get("snoozed_until", 0) > time.time() if control else False
            work = list(
                db.scalars(
                    select(NotificationOutbox)
                    .where(
                        NotificationOutbox.status == "queued",
                        NotificationOutbox.available_at <= time.time(),
                    )
                    .order_by(NotificationOutbox.available_at)
                    .limit(50)
                )
            )
            for item in work:
                rule_row, event = (
                    db.get(NotificationRule, item.rule_id),
                    db.get(Event, item.event_id),
                )
                if (
                    not rule_row
                    or not event
                    or not rule_row.values["enabled"]
                    or snoozed
                    or item.expires_at <= time.time()
                    or not in_schedule(rule_row.values, now)
                ):
                    item.status = "expired"
                    continue
                rule = rule_row.values
                observation = (
                    db.scalar(
                        select(Analysis.observation)
                        .where(Analysis.event_id == event.id)
                        .order_by(Analysis.revision.desc())
                        .limit(1)
                    )
                    if item.kind != "initial"
                    else None
                )
                if not matches(rule, observation):
                    item.status = "expired"
                    continue
                tag = f"{event.id}:{item.rule_id}"
                existing = db.scalar(select(Notification).where(Notification.tag == tag))
                body = (
                    event.summary
                    if rule["privacy_mode"] == "descriptive"
                    and item.kind != "initial"
                    and match_kind(rule, observation) == "known"
                    and event.summary
                    else "New camera activity. Open Porchlight to review the recording."
                )
                if body == event.summary and self.face_contexts:
                    context = self.face_contexts([event.id]).get(event.id, FaceDescription())
                    body = personalize_summary(body, context) or body
                if item.kind == "faces" and body == event.summary:
                    item.status = "expired"
                    continue
                if (
                    item.kind == "faces"
                    and item.channel == "in_app"
                    and existing
                    and existing.body == body
                ):
                    item.status = "transport_accepted"
                    continue
                if item.channel == "web_push" and self.push:
                    self.push.fanout(db, item, body)
                    continue
                if item.channel != "in_app":
                    item.status, item.safe_error = "blocked", "TRANSPORT_NOT_CONFIGURED"
                    continue
                if existing:
                    existing.body = body
                    item.status = "transport_accepted"
                    continue
                last = db.scalar(
                    select(Notification.created_at)
                    .where(Notification.rule_id == item.rule_id)
                    .order_by(Notification.created_at.desc())
                    .limit(1)
                )
                if (
                    last
                    and (now - datetime.fromisoformat(last)).total_seconds()
                    < rule["cooldown_seconds"]
                ):
                    item.status = "expired"
                    continue
                db.add(
                    Notification(
                        id=str(uuid4()),
                        event_id=event.id,
                        rule_id=item.rule_id,
                        tag=tag,
                        title="Porchlight activity",
                        body=body,
                        created_at=now.isoformat(),
                        read=False,
                    )
                )
                item.status = "transport_accepted"
            db.commit()

    def notify_work(self) -> None:
        self.wake.set()

    async def run(self) -> None:
        while True:
            self.wake.clear()
            self.last_tick = time.time()
            try:
                await local_work(self.dispatch)
                if self.push:
                    self.push.notify_work()
            except Exception:
                logging.getLogger("porchlight").error('{"event":"notification_worker_retry"}')
            try:
                await asyncio.wait_for(self.wake.wait(), 2)
            except TimeoutError:
                pass
