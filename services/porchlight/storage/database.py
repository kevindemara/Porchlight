from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config as MigrationConfig
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "porchlight.db"
        self.engine = create_engine(
            URL.create("sqlite", database=str(self.path)),
            connect_args={"check_same_thread": False, "timeout": 10},
        )
        event.listen(self.engine, "connect", self._configure)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _configure(connection: Any, _: Any) -> None:
        def daypart(instant: str, timezone: str) -> str:
            try:
                hour = datetime.fromisoformat(instant).astimezone(ZoneInfo(timezone)).hour
                return (
                    "morning"
                    if 6 <= hour < 12
                    else "afternoon"
                    if 12 <= hour < 17
                    else "evening"
                    if 17 <= hour < 21
                    else "night"
                )
            except (ValueError, TypeError, KeyError):
                return "unknown"

        connection.create_function("porchlight_daypart", 2, daypart, deterministic=True)
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

    def migrate(self) -> None:
        config = MigrationConfig()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    def session(self) -> Session:
        return self.sessions()

    def close(self) -> None:
        self.engine.dispose()


def current_revision(engine: Engine) -> str:
    with engine.connect() as connection:
        from sqlalchemy import text

        return str(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one())
