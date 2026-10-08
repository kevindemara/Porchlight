import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from porchlight.api.contracts import ApiError
from porchlight.search import date_range, validate_intent
from porchlight.storage.models import Event


def test_digest_full_status_counts_exceed_highlight_limit(authenticated, synthetic_mp4) -> None:
    client, headers = authenticated
    event = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    ).json()
    with client.app.state.db.session() as db:
        for index in range(510):
            identifier = str(uuid4())
            db.add(
                Event(
                    id=identifier,
                    source_key=f"synthetic:{identifier}",
                    source_type="manual_import",
                    media_id=event["media_id"],
                    captured_at="2026-10-07T12:00:00+00:00",
                    discovered_at="2026-10-07T12:00:00+00:00",
                    timestamp_quality="explicit",
                    analysis_status="analyzed" if index < 505 else "analysis_failed",
                )
            )
        db.commit()
    result = client.get("/api/v1/digests/daily?day=2026-10-07").json()
    assert result["analyzed_count"] == 505 and result["failed_count"] == 5
    assert result["truncated"] and "latest 500" in result["coverage_note"]


def intent() -> dict:
    return {
        "schema_version": "1.0",
        "text_query": "",
        "camera_ids": [],
        "categories": ["vehicle"],
        "color": "black",
        "time_range": {"preset": "yesterday", "start": None, "end": None, "daypart": "evening"},
        "favorites_only": False,
        "needs_clarification": False,
        "clarification": None,
    }


def test_relative_search_dates_resolve_locally_and_handle_dst() -> None:
    value = validate_intent(
        json.dumps(intent()), [], "America/Toronto", datetime(2026, 10, 7, 1, tzinfo=UTC)
    )
    assert value.filters.start == datetime(2026, 10, 5, 4, tzinfo=UTC)
    assert value.filters.end == datetime(2026, 10, 6, 4, tzinfo=UTC)
    assert value.filters.categories == ["vehicle"]
    assert value.filters.daypart == "evening"
    for day, expected_hours in [("2026-03-08", 23), ("2026-11-01", 25)]:
        start, end = date_range(datetime.fromisoformat(day).date(), "America/Toronto")
        assert (end - start).total_seconds() / 3600 == expected_hours


@pytest.mark.parametrize(
    "change",
    [
        {"camera_ids": ["00000000-0000-0000-0000-000000000001"]},
        {"sql": "DELETE FROM events"},
        {"categories": ["identity"]},
        {
            "time_range": {
                "preset": "custom",
                "start": "2026-10-07T00:00:00Z",
                "end": "2026-10-06T00:00:00Z",
                "daypart": "all",
            }
        },
        {
            "time_range": {
                "preset": "today",
                "start": "2026-10-07T00:00:00Z",
                "end": None,
                "daypart": "all",
            }
        },
    ],
)
def test_untrusted_search_interpretation_is_rejected(change: dict) -> None:
    with pytest.raises(ApiError):
        validate_intent(
            json.dumps({**intent(), **change}), [], "America/Toronto", datetime.now(UTC)
        )
