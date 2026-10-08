from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, Protocol

from porchlight.api.contracts import ApiError


class SecretStore(Protocol):
    def read(self) -> dict[str, Any] | None: ...
    def write(self, value: dict[str, Any]) -> None: ...


class WindowsVault:
    """Current-Windows-user DPAPI envelope; never falls back to plaintext."""

    def __init__(self, root: Path, purpose: Literal["blink", "push", "faces"] = "blink"):
        self.path = root / f"secrets/{purpose}.dpapi"
        self.entropy = f"porchlight-{purpose}-v1".encode()

    @staticmethod
    def unavailable() -> ApiError:
        return ApiError(
            503,
            "VAULT_UNAVAILABLE",
            "The Windows credential vault is unavailable. No plaintext credentials were saved.",
        )

    def read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            import win32crypt

            _, decrypted = win32crypt.CryptUnprotectData(
                self.path.read_bytes(), self.entropy, None, None, 1
            )
            result = json.loads(decrypted)
            if not isinstance(result, dict):
                raise ValueError("Invalid vault shape")
            return dict(result)
        except Exception as exc:
            raise self.unavailable() from exc

    def write(self, value: dict[str, Any]) -> None:
        try:
            import win32crypt

            encrypted = win32crypt.CryptProtectData(
                json.dumps(value).encode(),
                "Porchlight private configuration",
                self.entropy,
                None,
                None,
                1,
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".part")
            with temporary.open("wb") as handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception as exc:
            raise self.unavailable() from exc
