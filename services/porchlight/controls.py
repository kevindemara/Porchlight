"""Explicit manual device commands, serialized by the provider and never replayed."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from porchlight.api.contracts import ApiError, CameraCommandRequest, CameraCommandView
from porchlight.providers.base import CameraControlProvider
from porchlight.storage.database import Database
from porchlight.storage.models import CameraCommand


def view(row: CameraCommand) -> CameraCommandView:
    return CameraCommandView.model_validate(
        {
            key: getattr(row, key)
            for key in (
                "id",
                "camera_id",
                "operation",
                "desired",
                "state",
                "observed",
                "safe_error",
                "created_at",
            )
        }
    )


class CameraControls:
    def __init__(
        self, db: Database, provider: CameraControlProvider, session_valid: Callable[[str], bool]
    ):
        self.db, self.provider, self.session_valid = db, provider, session_valid
        self.tasks: dict[str, asyncio.Task[None]] = {}
        with db.session() as session:
            for row in session.scalars(
                select(CameraCommand).where(CameraCommand.state.in_(["pending", "sending"]))
            ):
                row.state, row.safe_error = "unknown", "RESTART_BEFORE_READBACK"
            session.commit()

    def get(self, identifier: str) -> CameraCommandView:
        with self.db.session() as session:
            row = session.get(CameraCommand, identifier)
            if not row:
                raise ApiError(
                    404, "CAMERA_COMMAND_NOT_FOUND", "This camera command is unavailable."
                )
            return view(row)

    def latest(self, camera_id: str, operation: str | None = None) -> CameraCommandView | None:
        with self.db.session() as session:
            statement = select(CameraCommand).where(CameraCommand.camera_id == camera_id)
            if operation:
                statement = statement.where(CameraCommand.operation == operation)
            row = session.scalar(
                statement.order_by(CameraCommand.created_at.desc(), CameraCommand.id.desc()).limit(
                    1
                )
            )
            return view(row) if row else None

    def submit(self, camera_id: str, body: CameraCommandRequest, actor: str) -> CameraCommandView:
        identifier = str(UUID(body.request_id))
        if not body.desired and not body.confirm_disable:
            raise ApiError(
                409, "DISABLE_CONFIRMATION_REQUIRED", "Confirm disabling this Blink control."
            )
        with self.db.session() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            previous = session.get(CameraCommand, identifier)
            if previous:
                if (previous.camera_id, previous.operation, previous.desired) != (
                    camera_id,
                    body.operation,
                    body.desired,
                ):
                    raise ApiError(
                        409, "COMMAND_ID_REUSED", "Use a new request for a different camera action."
                    )
                return view(previous)
            if session.scalar(
                select(CameraCommand.id)
                .where(CameraCommand.state.in_(["pending", "sending"]))
                .limit(1)
            ):
                raise ApiError(
                    409, "CAMERA_CONTROL_BUSY", "Wait for the current camera command to finish."
                )
            latest = session.scalar(
                select(CameraCommand.created_at).order_by(CameraCommand.created_at.desc()).limit(1)
            )
            if latest and time.time() - datetime.fromisoformat(latest).timestamp() < 10:
                raise ApiError(
                    429,
                    "CAMERA_CONTROL_WAIT",
                    "Wait ten seconds between camera commands.",
                    retry_after=10,
                )
            camera = next(
                (camera for camera in self.provider.cameras if camera.id == camera_id), None
            )
            available = camera and (
                camera.network_control
                if body.operation == "network_armed"
                else camera.motion_control
            )
            if not available:
                raise ApiError(
                    409,
                    "CONTROL_UNVERIFIED",
                    "Blink has not exposed a readable state for this control.",
                )
            row = CameraCommand(
                id=identifier,
                camera_id=camera_id,
                actor=actor,
                operation=body.operation,
                desired=body.desired,
                state="pending",
                observed=None,
                safe_error=None,
                created_at=datetime.now(UTC).isoformat(),
            )
            session.add(row)
            session.commit()
            result = view(row)
        self.tasks[identifier] = asyncio.create_task(self.send(identifier))
        return result

    async def send(self, identifier: str) -> None:
        try:
            with self.db.session() as session:
                row = session.get(CameraCommand, identifier)
                assert row
                if not self.session_valid(row.actor):
                    row.state, row.safe_error = "failed", "SESSION_EXPIRED"
                    session.commit()
                    return
                row.state = "sending"
                session.commit()
            try:
                async with asyncio.timeout(30):
                    observed = await self.provider.set_camera_state(
                        row.camera_id,
                        row.operation,
                        row.desired,
                        lambda: self.session_valid(row.actor),
                    )
                self.finish(identifier, observed)
            except asyncio.CancelledError:
                self.finish(identifier, None, "STOPPED_BEFORE_READBACK")
                raise
            except ApiError as error:
                self.finish(identifier, None, error.code)
            except Exception:
                self.finish(identifier, None, "CAMERA_READBACK_UNAVAILABLE")
        finally:
            self.tasks.pop(identifier, None)

    def finish(
        self, identifier: str, observed: bool | None, error: str | None = None
    ) -> CameraCommandView:
        with self.db.session() as session:
            row = session.get(CameraCommand, identifier)
            assert row
            row.observed = observed
            row.state = (
                "confirmed" if observed is not None and observed == row.desired else "unknown"
            )
            row.safe_error = error or (None if row.state == "confirmed" else "READBACK_UNCONFIRMED")
            session.commit()
            return view(row)

    async def verify(self, identifier: str) -> CameraCommandView:
        command = self.get(identifier)
        if command.state in {"pending", "sending"}:
            raise ApiError(409, "CAMERA_CONTROL_BUSY", "Wait for the command's read-back.")
        try:
            async with asyncio.timeout(30):
                observed = await self.provider.verify_camera_state(
                    command.camera_id, command.operation
                )
            return self.finish(identifier, observed)
        except ApiError as error:
            return self.finish(identifier, None, error.code)
        except Exception:
            return self.finish(identifier, None, "CAMERA_READBACK_UNAVAILABLE")

    async def close(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
