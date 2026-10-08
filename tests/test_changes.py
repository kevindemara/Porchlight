import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError
from porchlight.changes import TOPICS, StateChanges
from porchlight.config import Config
from porchlight.storage.database import Database


def test_change_log_is_transactional_bounded_replayed_and_private(config: Config) -> None:
    db = Database(config.data_root)
    db.migrate()
    changes = StateChanges(db, lambda _: True)
    try:
        kind, cursor, topics = changes.read(None)
        assert kind == "resync" and set(topics) == TOPICS
        with db.engine.connect() as connection:
            connection.exec_driver_sql(
                "INSERT INTO camera_metadata(camera_id,name,\"group\") "
                "VALUES('synthetic-id','private label','')"
            )
            connection.rollback()
        assert changes.read(cursor) == ("change", cursor, [])
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO camera_metadata(camera_id,name,\"group\") "
                "VALUES('synthetic-id','private label','')"
            )
        kind, next_cursor, topics = changes.read(cursor)
        assert kind == "change" and next_cursor != cursor and topics == ["cameras"]
        frame = changes.frame(kind, next_cursor, topics)
        assert b"private label" not in frame and b"synthetic-id" not in frame
        assert changes.read(next_cursor) == ("change", next_cursor, [])
        with db.engine.begin() as connection:
            for number in range(700):
                connection.exec_driver_sql(
                    "UPDATE camera_metadata SET name=? WHERE camera_id='synthetic-id'",
                    (str(number),),
                )
            assert (
                connection.exec_driver_sql("SELECT COUNT(*) FROM state_changes").scalar_one() == 512
            )
        assert changes.read(cursor)[0] == "resync"
        current = changes.read(None)[1]
        # Replay is bounded per batch and advances through all retained invalidations.
        start = int(current.split(":")[1]) - 512
        kind, middle, topics = changes.read(f"{changes.epoch}:{start}")
        assert kind == "change" and int(middle.split(":")[1]) == start + 128
        assert topics == ["cameras"]
        assert StateChanges(db, lambda _: True).read(current)[0] == "resync"
        for malformed in ("x\nprivate", f"{changes.epoch}:9999999999999999999", "a" * 10000):
            assert changes.read(malformed)[0] == "resync"
    finally:
        db.close()


def test_stream_stops_on_session_revocation_disconnect_and_releases_slots(config: Config) -> None:
    db = Database(config.data_root)
    db.migrate()
    valid = True
    changes = StateChanges(db, lambda _: valid)

    class Request:
        disconnected = False

        async def is_disconnected(self) -> bool:
            return self.disconnected

    async def run() -> None:
        nonlocal valid
        request = Request()
        token = changes.reserve("actor")
        stream = changes.stream(request, "actor", token, None)  # type: ignore[arg-type]
        assert await anext(stream) == b"retry: 5000\n\n"
        assert b"event: resync" in await anext(stream)
        valid = False
        assert await anext(stream) == b"event: session_expired\ndata: {}\n\n"
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        assert not changes.connections
        valid = True
        token = changes.reserve("actor")
        stream = changes.stream(request, "actor", token, None)  # type: ignore[arg-type]
        await anext(stream)
        request.disconnected = True
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        assert not changes.connections

    try:
        asyncio.run(run())
    finally:
        db.close()


def test_stream_api_auth_headers_capacity_and_cleanup(
    authenticated: tuple[TestClient, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = authenticated
    changes = client.app.state.changes

    async def finite(*args: Any) -> Any:
        yield b'event: resync\ndata: {"topics":["activity"]}\n\n'

    monkeypatch.setattr(changes, "stream", finite)
    result = client.get("/api/v1/stream")
    assert result.status_code == 200 and result.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert (
        result.headers["cache-control"] == "no-store"
        and result.headers["x-accel-buffering"] == "no"
    )
    assert not changes.connections
    assert (
        client.get("/api/v1/stream", headers={"Origin": "https://bad.invalid"}).status_code == 403
    )
    client.cookies.clear()
    assert client.get("/api/v1/stream").status_code == 401
    tokens = [changes.reserve("synthetic-one") for _ in range(4)]
    with pytest.raises(ApiError) as error:
        changes.reserve("synthetic-one")
    assert error.value.code == "STREAM_LIMIT"
    for index in range(12):
        tokens.append(changes.reserve(f"synthetic-{index + 2}"))
    with pytest.raises(ApiError):
        changes.reserve("other")
    for token in tokens:
        changes.release(token)
        changes.release(token)
    assert not changes.connections
    changes.closing = True
    with pytest.raises(ApiError) as error:
        changes.reserve("other")
    assert error.value.code == "STREAM_STOPPING"
