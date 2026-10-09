from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.storage.models import Capture, Event, MediaAsset

from tests.test_faces import store


def seed_capture(client: TestClient, **changes: object) -> str:
    values = dict(
        id=str(uuid4()),
        camera_id="synthetic-camera",
        camera_name="Synthetic porch 100%",
        kind="snapshot",
        state="ready",
        saved_at="2026-10-08T12:00:00+00:00",
        bytes=100,
        width=320,
        height=240,
        duration_seconds=None,
        sha256=None,
        safe_error=None,
        favourite=False,
    )
    values.update(changes)
    with client.app.state.db.session() as db:
        db.add(Capture(**values))
        db.commit()
    return str(values["id"])


def test_mixed_timeline_pagination_ties_and_source_identity(authenticated):
    client, _ = authenticated
    instant = "2026-10-08T12:00:00+00:00"
    expected = []
    for index in range(36):
        event_id = store(
            client.app.state.db, client.app.state.config, captured_at=instant
        )
        capture_id = seed_capture(client, id=event_id if index == 0 else str(uuid4()))
        expected.extend([(event_id, False), (capture_id, True)])
    expected.sort(key=lambda pair: (pair[0], pair[1]), reverse=True)
    found, cursor = [], None
    for _ in range(4):
        params = {"include_captures": True}
        if cursor:
            params["cursor"] = cursor
        response = client.get("/api/v1/events", params=params)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 30
        found.extend((item["id"], item["capture"] is not None) for item in data["items"])
        cursor = data["next_cursor"]
        if cursor is None:
            break
        assert cursor.startswith(("e:", "c:"))
    assert found == expected
    legacy = client.get("/api/v1/events").json()
    assert all(item["capture"] is None for item in legacy["items"])
    assert not legacy["next_cursor"].startswith(("e:", "c:"))


def test_capture_and_import_media_filters_are_server_side(authenticated):
    client, _ = authenticated
    video = store(client.app.state.db, client.app.state.config)
    image = store(client.app.state.db, client.app.state.config)
    with client.app.state.db.session() as db:
        event = db.get(Event, image)
        db.get(MediaAsset, event.media_id).media_type = "image/jpeg"
        db.commit()
    recording = seed_capture(client, kind="recording", duration_seconds=10)
    snapshot = seed_capture(client)

    def ids(**filters):
        response = client.get("/api/v1/events", params={"include_captures": True, **filters})
        assert response.status_code == 200
        return {item["id"] for item in response.json()["items"]}

    assert ids() == {video, image, recording, snapshot}
    assert ids(media_kind="recordings") == {video, recording}
    assert ids(media_kind="snapshots") == {image, snapshot}
    assert ids(source="live_capture") == {recording, snapshot}
    assert ids(source="live_snapshot") == {snapshot}
    assert ids(source="manual_import") == {video, image}
    assert ids(source="live_capture", category="person") == set()
    assert ids(source="live_capture", analysis="analyzed") == set()
    assert ids(source="live_capture", analysis="not_analyzed") == {recording, snapshot}


def test_capture_filter_search_favourites_camera_time_and_unknown_preservation(authenticated):
    client, _ = authenticated
    early = seed_capture(client, state="failed", safe_error="interrupted")
    late = seed_capture(
        client,
        kind="recording",
        saved_at="2026-10-08T22:00:00+00:00",
        favourite=True,
        camera_id="other",
    )

    def ids(**filters):
        return {
            row["id"]
            for row in client.get(
                "/api/v1/events",
                params={
                    "include_captures": True,
                    **filters,
                },
            ).json()["items"]
        }

    assert ids() == {early, late}
    assert ids(query="100%") == {early, late}
    assert ids(query="100_") == set()
    assert ids(favourites=True) == {late}
    assert ids(camera_id="synthetic-camera") == {early}
    assert ids(camera_ids=["other"]) == {late}
    assert ids(start="2026-10-08T21:00:00Z") == {late}
    assert ids(end="2026-10-08T22:00:00Z") == {early}
    assert ids(daypart="evening") == {late}
    for params in (
        {"cursor": "x:invalid"},
        {"cursor": "c:" + str(uuid4())},
        {"start": "2026-10-09T00:00:00Z", "end": "2026-10-08T00:00:00Z"},
        {"query": "\x00"},
    ):
        assert (
            client.get("/api/v1/events", params={"include_captures": True, **params}).status_code
            == 422
        )


def test_captures_beyond_first_page_are_filtered_before_pagination(authenticated):
    client, _ = authenticated
    newest = datetime(2026, 10, 8, 12, tzinfo=UTC)
    for index in range(40):
        seed_capture(
            client, kind="recording", saved_at=(newest - timedelta(minutes=index)).isoformat()
        )
    oldest = seed_capture(client, saved_at=(newest - timedelta(days=1)).isoformat())
    response = client.get(
        "/api/v1/events", params={"include_captures": True, "media_kind": "snapshots"}
    )
    assert [row["id"] for row in response.json()["items"]] == [oldest]


def test_unified_feed_remains_authenticated(client: TestClient):
    assert client.get("/api/v1/events?include_captures=true").status_code == 401


@pytest.mark.parametrize("kind", ["recording", "snapshot"])
def test_capture_result_keeps_original_library_contract(authenticated, kind):
    client, _ = authenticated
    identifier = seed_capture(client, kind=kind, state="saving")
    row = client.get("/api/v1/events?include_captures=true").json()["items"][0]
    assert row["id"] == identifier and row["source_type"] == f"live_{kind}"
    assert row["capture"] == client.get(f"/api/v1/library/{identifier}").json()
    assert row["analysis_status"] == "not_analyzed"
    assert not row["object_categories"] and not row["recognized_people"]
