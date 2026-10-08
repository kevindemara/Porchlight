from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from porchlight.api.contracts import BlinkCredentials, BlinkStatus, BlinkVerification, CameraView


@dataclass(frozen=True)
class ClipReference:
    source_key: str
    camera_id: str | None
    captured_at: str | None
    raw_timestamp: str
    media_path: str
    deleted: bool


@dataclass(frozen=True)
class RecordingPage:
    clips: list[ClipReference]
    exhausted: bool


class RecordingProvider(Protocol):
    @property
    def recording_source_id(self) -> str: ...
    async def recording_page(self, since: float, page: int) -> RecordingPage: ...
    async def download_recording(self, media_path: str, destination: Path) -> None: ...


class CameraProvider(Protocol):
    async def begin_auth(self, credentials: BlinkCredentials, actor: str) -> BlinkStatus: ...
    async def complete_auth(self, verification: BlinkVerification, actor: str) -> BlinkStatus: ...
    async def discover_inventory(self) -> list[CameraView]: ...
    async def restore_session(self) -> None: ...
    async def close(self) -> None: ...


class CameraControlProvider(Protocol):
    cameras: list[CameraView]

    async def set_camera_state(
        self,
        camera_id: str,
        operation: str,
        desired: bool,
        is_authorized: Callable[[], bool] | None = None,
    ) -> bool | None: ...
    async def verify_camera_state(self, camera_id: str, operation: str) -> bool | None: ...


class LiveInput(Protocol):
    async def read(self) -> bytes: ...
    async def close(self) -> None: ...


class LiveProvider(Protocol):
    async def open_live(self, camera_id: str) -> LiveInput: ...
