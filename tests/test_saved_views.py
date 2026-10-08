from datetime import UTC, datetime

from porchlight.api.contracts import EventFilters


def test_saved_filters_are_authenticated_typed_persistent_and_do_not_need_ai(authenticated) -> None:
    client, headers = authenticated
    filters = EventFilters(
        query="owner note %",
        favourites=True,
        categories=["vehicle"],
        color="black",
        start=datetime(2026, 10, 1, tzinfo=UTC),
    )
    body = {"name": "  Black cars  ", "filters": filters.model_dump(mode="json")}
    assert client.post("/api/v1/saved-views", json=body).status_code == 403
    result = client.post("/api/v1/saved-views", headers=headers, json=body)
    assert result.status_code == 201
    row = result.json()
    assert row["name"] == "Black cars"
    assert row["filters"]["categories"] == ["vehicle"]
    assert client.get(f"/api/v1/saved-views/{row['id']}").json() == row
    assert client.get("/api/v1/saved-views").json() == [row]
    assert not client.get("/api/v1/settings").json()["ai_enabled"]
    assert client.delete(f"/api/v1/saved-views/{row['id']}", headers=headers).status_code == 204
    assert client.get("/api/v1/saved-views").json() == []


def test_saved_view_rejects_cursor_invalid_filters_and_whitespace(authenticated) -> None:
    client, headers = authenticated
    for body in [
        {"name": " ", "filters": {}},
        {"name": "Invalid", "filters": {"categories": ["identity"]}},
        {"name": "Invalid", "filters": {"cursor": "arbitrary"}},
        {"name": "Invalid", "filters": {"sql": "DROP TABLE events"}},
        {
            "name": "Invalid",
            "filters": {"start": "2026-10-07T00:00:00Z", "end": "2026-10-06T00:00:00Z"},
        },
    ]:
        assert client.post("/api/v1/saved-views", headers=headers, json=body).status_code == 422
    assert client.get("/api/v1/saved-views").json() == []
