from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Callable
from functools import partial
from uuid import uuid4

from fastapi import Request

from porchlight.api.contracts import ApiError
from porchlight.storage.database import Database
from porchlight.storage.work import local_work

TOPICS = {"activity", "cameras", "settings", "notifications", "library", "health"}
CURSOR = re.compile(r"^([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}):([0-9]{1,19})$")


class StateChanges:
    """Topic invalidations only. Ordinary authenticated queries remain authoritative."""

    def __init__(self, db: Database, valid_session: Callable[[str], bool]):
        self.db, self.valid_session = db, valid_session
        self.epoch = str(uuid4())
        self.connections: dict[str, str] = {}
        self.closing = False

    def reserve(self, actor: str) -> str:
        if self.closing:
            raise ApiError(503, "STREAM_STOPPING", "Porchlight is shutting down.", True)
        if len(self.connections) >= 16 or list(self.connections.values()).count(actor) >= 4:
            raise ApiError(429, "STREAM_LIMIT", "Too many open update streams.", True, 15)
        token = str(uuid4())
        self.connections[token] = actor
        return token

    def release(self, token: str) -> None:
        self.connections.pop(token, None)

    def read(self, cursor: str | None) -> tuple[str, str, list[str]]:
        with self.db.engine.connect() as db:
            db.exec_driver_sql("BEGIN")
            minimum, maximum = db.exec_driver_sql(
                "SELECT COALESCE(MIN(id),0),COALESCE(MAX(id),0) FROM state_changes"
            ).one()
            match = CURSOR.fullmatch(cursor or "")
            previous = int(match[2]) if match else -1
            if (
                not match
                or match[1] != self.epoch
                or previous > maximum
                or previous < max(0, minimum - 1)
            ):
                return "resync", f"{self.epoch}:{maximum}", sorted(TOPICS)
            rows = db.exec_driver_sql(
                "SELECT id,topics FROM state_changes WHERE id>? ORDER BY id LIMIT 128",
                (previous,),
            ).all()
            topics = {topic for _, value in rows for topic in value.split(",") if topic in TOPICS}
            return "change", f"{self.epoch}:{rows[-1][0] if rows else previous}", sorted(topics)

    @staticmethod
    def frame(kind: str, cursor: str, topics: list[str]) -> bytes:
        payload = json.dumps({"topics": topics}, separators=(",", ":"))
        return f"event: {kind}\nid: {cursor}\ndata: {payload}\n\n".encode()

    async def stream(
        self, request: Request, actor: str, token: str, cursor: str | None
    ) -> AsyncIterator[bytes]:
        started, heartbeat = time.monotonic(), time.monotonic()
        try:
            yield b"retry: 5000\n\n"
            while time.monotonic() - started < 300:
                if await request.is_disconnected() or self.closing:
                    return
                if not await local_work(lambda: self.valid_session(actor)):
                    yield b"event: session_expired\ndata: {}\n\n"
                    return
                kind, next_cursor, topics = await local_work(partial(self.read, cursor))
                if topics:
                    yield self.frame(kind, next_cursor, topics)
                    cursor = next_cursor
                if time.monotonic() - heartbeat >= 15:
                    yield b": keepalive\n\n"
                    heartbeat = time.monotonic()
                await asyncio.sleep(1)
        finally:
            self.release(token)
