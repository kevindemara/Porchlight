from pathlib import Path
from typing import TextIO

import portalocker


class InstanceLock:
    def __init__(self, root: Path):
        self.root = root
        self.handle: TextIO | None = None

    def acquire(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        handle = (self.root / "instance.lock").open("a+")
        try:
            portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.exceptions.LockException as exc:
            handle.close()
            raise RuntimeError("Porchlight is already running for this data folder.") from exc
        self.handle = handle

    def release(self) -> None:
        if self.handle:
            portalocker.unlock(self.handle)
            self.handle.close()
            self.handle = None
