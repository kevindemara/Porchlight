from __future__ import annotations

import ctypes
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


def default_data_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "Porchlight"


def is_remote_volume(path: Path) -> bool:
    if os.name != "nt":
        return False
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel.GetDriveTypeW
    query.argtypes, query.restype = [ctypes.c_wchar_p], ctypes.c_uint
    return int(query(path.anchor)) == 4  # DRIVE_REMOTE, including mapped network drives.


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORCHLIGHT_", extra="forbid")
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    timezone: str = "America/Toronto"
    data_root: Path = Field(default_factory=default_data_root)
    web_dist: Path = ROOT / "apps/web/dist"
    ollama_url: str = "http://127.0.0.1:11434"
    dev_frontend: bool = False
    public_origin: str | None = None
    cloud_poll_seconds: int = Field(default=60, ge=30, le=3600)
    ffmpeg: Path | None = None
    ffprobe: Path | None = None
    face_model: Path = Path(
        "C:/local-models/yunet-face-detection/face_detection_yunet_2023mar.onnx"
    )
    sface_model: Path = Path(
        "C:/local-models/sface-recognition/face_recognition_sface_2021dec.onnx"
    )

    @field_validator("host")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        if value != "127.0.0.1":
            raise ValueError(
                "Porchlight binds to loopback only; "
                "use the configured local proxy for remote access."
            )
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Choose an IANA timezone, such as America/Toronto.") from exc
        return value

    @field_validator("public_origin")
    @classmethod
    def explicit_https_origin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        url = urlsplit(value)
        hostname = url.hostname or ""
        if (
            url.scheme != "https"
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
            or url.port not in {None, 443}
            or not re.fullmatch(r"(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", hostname)
            or "." not in hostname
            or ".." in hostname
            or "*" in hostname
            or hostname in {"localhost", "127.0.0.1"}
            or all(character.isdigit() or character == "." for character in hostname)
        ):
            raise ValueError("Use one explicit HTTPS domain origin on port 443, without a path.")
        return f"https://{url.netloc.lower()}"

    @field_validator("ollama_url")
    @classmethod
    def local_ai_only(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme != "http"
            or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
            or url.username
            or url.password
            or url.port != 11434
        ):
            raise ValueError("Ollama must use loopback HTTP on port 11434 without credentials.")
        return value.rstrip("/")

    @model_validator(mode="after")
    def local_data(self) -> Config:
        self.data_root = self.data_root.expanduser().resolve()
        if str(self.data_root).startswith("\\\\") or "onedrive" in str(self.data_root).lower():
            raise ValueError("Runtime data must be on a local disk outside OneDrive.")
        if is_remote_volume(self.data_root):
            raise ValueError("Runtime data cannot use a mapped network drive; choose a local disk.")
        if self.data_root.is_relative_to(ROOT):
            raise ValueError("Keep runtime data outside the source repository.")
        return self

    @property
    def allowed_origins(self) -> set[str]:
        origins = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
        if self.dev_frontend:
            origins.add("http://127.0.0.1:5174")
        if self.public_origin:
            origins.add(self.public_origin)
        return origins

    @property
    def allowed_hosts(self) -> set[str]:
        hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        if self.public_origin:
            hosts.add(urlsplit(self.public_origin).netloc)
        return hosts

    def tool_path(self, name: str) -> str | None:
        configured = self.ffmpeg if name == "ffmpeg" else self.ffprobe
        if configured:
            return str(configured.resolve()) if configured.is_file() else None
        installed = default_data_root() / "tools/ffmpeg/bin" / f"{name}.exe"
        return str(installed) if installed.is_file() else shutil.which(name)
