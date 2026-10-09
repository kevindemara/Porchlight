"""One bounded read-only timeline for archived events and explicit live captures."""

from __future__ import annotations

from sqlalchemy import Select, and_, false, func, or_, select
from sqlalchemy.orm import Session

from porchlight.api.contracts import ApiError, CaptureView, EventFilters, EventView
from porchlight.catalog import event_query
from porchlight.storage.models import Capture, Event, MediaAsset


def capture_query(filters: EventFilters, timezone: str) -> Select[Capture]:
    result = select(Capture)
    if (
        not filters.include_captures
        or (
            filters.source
            and filters.source not in {"live_capture", "live_recording", "live_snapshot"}
        )
        or filters.categories
        or filters.category
        or filters.color
        or filters.direction
        or filters.action
    ):
        return result.where(false())
    if filters.analysis and filters.analysis != "not_analyzed":
        return result.where(false())
    if filters.media_kind != "all":
        result = result.where(
            Capture.kind == ("recording" if filters.media_kind == "recordings" else "snapshot")
        )
    if filters.source in {"live_recording", "live_snapshot"}:
        result = result.where(
            Capture.kind == ("recording" if filters.source == "live_recording" else "snapshot")
        )
    if filters.camera_id:
        result = result.where(Capture.camera_id == filters.camera_id)
    if filters.camera_ids:
        result = result.where(Capture.camera_id.in_(filters.camera_ids))
    if filters.favourites:
        result = result.where(Capture.favourite.is_(True))
    if filters.start:
        result = result.where(Capture.saved_at >= filters.start.isoformat())
    if filters.end:
        result = result.where(Capture.saved_at < filters.end.isoformat())
    if filters.daypart != "all":
        result = result.where(
            func.porchlight_daypart(Capture.saved_at, timezone) == filters.daypart
        )
    if filters.query:
        # Search literal saved metadata only, without inventing AI observations for captures.
        label = Capture.camera_name + " local live " + Capture.kind
        result = result.where(func.instr(func.lower(label), filters.query.lower()) > 0)
    return result


def timeline_rows(
    db: Session,
    filters: EventFilters,
    timezone: str,
) -> list[tuple[Event, MediaAsset] | Capture]:
    events = event_query(filters, timezone)
    captures = capture_query(filters, timezone)
    event_time = func.coalesce(Event.captured_at, Event.discovered_at)
    if filters.cursor:
        scope, separator, identifier = filters.cursor.partition(":")
        if separator and scope not in {"c", "e"}:
            raise ApiError(422, "INVALID_CURSOR", "Refresh Activity.")
        identifier = identifier if separator else filters.cursor
        previous = db.get(Event, identifier) if scope != "c" else None
        capture = db.get(Capture, identifier) if filters.include_captures and scope == "c" else None
        if previous is None and capture is None:
            raise ApiError(422, "INVALID_CURSOR", "Refresh Activity.")
        instant = (
            (previous.captured_at or previous.discovered_at)
            if previous
            else capture.saved_at
            if capture
            else ""
        )
        event_id_bound = Event.id <= identifier if capture else Event.id < identifier
        events = events.where(
            or_(event_time < instant, and_(event_time == instant, event_id_bound))
        )
        captures = captures.where(
            or_(
                Capture.saved_at < instant,
                and_(Capture.saved_at == instant, Capture.id < identifier),
            )
        )
    rows: list[tuple[Event, MediaAsset] | Capture] = [
        (event, asset)
        for event, asset in db.execute(
            events.order_by(event_time.desc(), Event.id.desc()).limit(31)
        ).all()
    ]
    if filters.include_captures:
        rows.extend(
            db.scalars(captures.order_by(Capture.saved_at.desc(), Capture.id.desc()).limit(31))
        )
    rows.sort(
        key=lambda row: (
            (row.saved_at, row.id, 1)
            if isinstance(row, Capture)
            else (row[0].captured_at or row[0].discovered_at, row[0].id, 0)
        ),
        reverse=True,
    )
    return rows[:31]


def capture_event(row: Capture) -> EventView:
    capture = CaptureView.model_validate(
        {key: getattr(row, key) for key in CaptureView.model_fields}
    )
    return EventView(
        id=row.id,
        source_type=f"live_{row.kind}",
        captured_at=row.saved_at,
        discovered_at=row.saved_at,
        timestamp_quality="local_capture",
        media_id=row.id,
        analysis_status="not_analyzed",
        summary=f"Live {row.kind} from {row.camera_name}",
        favourite=row.favourite,
        note="",
        duration_seconds=row.duration_seconds or 0,
        camera_id=row.camera_id,
        media_type="video/mp4" if row.kind == "recording" else "image/jpeg",
        capture=capture,
    )
