from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from sqlalchemy import func, select

from porchlight.ai.ollama import Ollama
from porchlight.api.contracts import (
    ApiError,
    CameraView,
    DailyDigest,
    DigestHighlight,
    EventFilters,
    SearchPreview,
)
from porchlight.catalog import event_query
from porchlight.config import ROOT
from porchlight.storage.database import Database
from porchlight.storage.models import Analysis, Event

SEARCH_SCHEMA = json.loads((ROOT / "schemas/search-query.schema.json").read_text(encoding="utf-8"))
SEARCH_PROMPT = (
    (ROOT / "prompts/SEARCH_QUERY_SYSTEM.md")
    .read_text(encoding="utf-8")
    .split("```text\n")[1]
    .split("```")[0]
)


def date_range(day: date, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    return (
        datetime.combine(day, time(), zone).astimezone(UTC),
        datetime.combine(day + timedelta(days=1), time(), zone).astimezone(UTC),
    )


def validate_intent(
    content: str, cameras: list[CameraView], timezone: str, now: datetime
) -> SearchPreview:
    try:
        if len(content) > 16 * 1024:
            raise ValueError("Oversized")
        value: Any = json.loads(content)
        Draft202012Validator(SEARCH_SCHEMA, format_checker=FormatChecker()).validate(value)
        if not set(value["camera_ids"]).issubset({camera.id for camera in cameras}):
            raise ValueError("Unknown camera")
        interval = value["time_range"]
        start, end = None, None
        preset = interval["preset"]
        if preset == "custom":
            if not interval["start"] or not interval["end"]:
                raise ValueError("Incomplete dates")
            start = datetime.fromisoformat(interval["start"])
            end = datetime.fromisoformat(interval["end"])
            if start >= end or end - start > timedelta(days=3650):
                raise ValueError("Invalid dates")
        else:
            if interval["start"] is not None or interval["end"] is not None:
                raise ValueError("Unexpected dates")
            today = now.astimezone(ZoneInfo(timezone)).date()
            if preset in {"today", "yesterday", "last_7_days"}:
                first = today - timedelta(
                    days=1 if preset == "yesterday" else 6 if preset == "last_7_days" else 0
                )
                start, _ = date_range(first, timezone)
                _, end = date_range(
                    today - timedelta(days=1) if preset == "yesterday" else today, timezone
                )
        filters = EventFilters(
            query=value["text_query"],
            camera_ids=value["camera_ids"],
            categories=value["categories"],
            color=value["color"],
            favourites=value["favorites_only"],
            start=start,
            end=end,
            daypart=interval["daypart"],
        )
        return SearchPreview(
            filters=filters,
            needs_clarification=value["needs_clarification"],
            message="Review and edit the proposed filters before searching."
            if not value["needs_clarification"]
            else "This request needs clarification. Choose or edit the filters manually.",
            timezone=timezone,
        )
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        raise ApiError(
            422,
            "INTERPRETATION_INVALID",
            "The interpretation was invalid. Choose filters manually.",
        ) from exc


async def interpret(
    ollama: Ollama, model: str | None, query: str, cameras: list[CameraView], timezone: str
) -> SearchPreview:
    now = datetime.now(UTC)
    content = await ollama.structured_text(
        model,
        SEARCH_SCHEMA,
        SEARCH_PROMPT,
        {
            "query": query,
            "now": now.isoformat(),
            "timezone": timezone,
            "cameras": [{"id": camera.id, "name": camera.name} for camera in cameras],
        },
    )
    return validate_intent(content, cameras, timezone, now)


def digest(db: Database, day: date, timezone: str) -> DailyDigest:
    start, end = date_range(day, timezone)
    filters = EventFilters(start=start, end=end)
    counts: dict[str, int] = {}
    highlights: list[DigestHighlight] = []
    with db.session() as session:
        statement = event_query(filters, timezone).order_by(
            func.coalesce(Event.captured_at, Event.discovered_at).desc(), Event.id.desc()
        )
        # Full counts are computed separately; highlights and category inspection are bounded.
        total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        filtered = statement.subquery()
        statuses: dict[str, int] = dict(
            session.execute(
                select(filtered.c.analysis_status, func.count()).group_by(
                    filtered.c.analysis_status
                )
            ).all()
        )
        rows = list(session.execute(statement.limit(500)))
        for event, _ in rows:
            observation = session.scalar(
                select(Analysis.observation)
                .where(Analysis.event_id == event.id)
                .order_by(Analysis.revision.desc())
                .limit(1)
            )
            entities = (
                event.corrected_entities
                if event.corrected_entities is not None
                else (observation or {}).get("entities", [])
            )
            for category in {entity["category"] for entity in entities}:
                counts[category] = counts.get(category, 0) + 1
            summary = event.corrected_summary or event.labels_summary or event.summary
            if len(highlights) < 8 and summary:
                highlights.append(
                    DigestHighlight(
                        text=summary[:500],
                        event_id=event.id,
                        source="owner"
                        if event.corrected_summary or event.corrected_entities is not None
                        else "ai",
                    )
                )
    return DailyDigest(
        date=day.isoformat(),
        timezone=timezone,
        recording_count=total,
        analyzed_count=int(statuses.get("analyzed", 0)),
        failed_count=int(statuses.get("analysis_failed", 0)),
        category_clip_counts=counts,
        highlights=highlights,
        truncated=total > 500,
        coverage_note="This digest covers saved recordings only. "
        "Continuous monitoring and retrieval coverage are not established. "
        "Categories use owner labels where supplied, otherwise the latest AI observation. "
        "Unanalyzed and failed clips may contain additional activity."
        + (" Counts by category cover only the latest 500 recordings." if total > 500 else ""),
    )
