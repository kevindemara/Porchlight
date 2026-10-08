from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.storage.models import Event, MediaAsset


@pytest.mark.parametrize("filtered", [False, True], ids=["activity", "search-favourites"])
def test_events_newest_recorded_first_across_pages(
    authenticated: tuple[TestClient, dict[str, str]], filtered: bool
) -> None:
    client, _ = authenticated
    asset_id = str(uuid4())
    start = datetime(2026, 10, 6, tzinfo=UTC)
    with client.app.state.db.session() as db:
        db.add(
            MediaAsset(
                id=asset_id,
                sha256="synthetic-ordering-fixture",
                relative_path="media/synthetic.mp4",
                bytes=1,
                duration_seconds=10,
                width=320,
                height=240,
            )
        )
        db.flush()
        for index in range(70):
            # Older clips are imported later; five equal recording times cross page one.
            minute = 38 if 38 <= index <= 42 else index
            captured = (start + timedelta(minutes=minute)).isoformat()
            discovered = (start + timedelta(minutes=200 - index)).isoformat()
            if index == 60:
                captured = None
                discovered = (start + timedelta(minutes=60)).isoformat()
            db.add(
                Event(
                    id=str(UUID(int=index + 1)),
                    source_type="blink_cloud" if captured else "manual_import",
                    source_key=f"synthetic-order:{index}",
                    captured_at=captured,
                    discovered_at=discovered,
                    timestamp_quality="upstream" if captured else "unknown",
                    media_id=asset_id,
                    analysis_status="not_analyzed",
                    note="matching fixture" if index % 2 == 0 else "other fixture",
                    favourite=index % 2 == 0,
                )
            )
        db.commit()

    params = {"query": "matching", "favourites": "true"} if filtered else {}
    expected = [
        str(UUID(int=index + 1))
        for index in reversed(range(70))
        if not filtered or index % 2 == 0
    ]
    seen: list[str] = []
    for _ in range(3):
        response = client.get("/api/v1/events", params=params)
        assert response.status_code == 200
        page = response.json()
        ids = [item["id"] for item in page["items"]]
        assert ids == expected[len(seen) : len(seen) + 30]
        seen.extend(ids)
        if not page["next_cursor"]:
            break
        params["cursor"] = page["next_cursor"]
    assert seen == expected
    assert len(set(seen)) == len(seen)
    assert client.get("/api/v1/events", params={"cursor": str(uuid4())}).status_code == 422
    client.cookies.clear()
    assert client.get("/api/v1/events").status_code == 401
