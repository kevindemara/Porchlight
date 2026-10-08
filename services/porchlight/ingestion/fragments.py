"""Bounded parser for our encoder's fragmented MP4; never parses arbitrary network media."""

from __future__ import annotations

import time

MAX_BOX = 4 * 1024 * 1024


class Fragments:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.header = b""
        self.initialized = False
        self.pending = b""
        self.started = 0.0

    def feed(self, data: bytes) -> list[tuple[float, bytes]]:
        self.buffer.extend(data)
        fragments = []
        while len(self.buffer) >= 8:
            size = int.from_bytes(self.buffer[:4], "big")
            kind = bytes(self.buffer[4:8])
            if size < 8 or size > MAX_BOX:
                raise ValueError("Unsupported encoder box")
            if len(self.buffer) < size:
                break
            box = bytes(self.buffer[:size])
            del self.buffer[:size]
            if kind in {b"ftyp", b"moov"} and not self.initialized:
                if len(self.header) + len(box) > MAX_BOX:
                    raise ValueError("Encoder header too large")
                self.header += box
                self.initialized = kind == b"moov" and self.header[4:8] == b"ftyp"
            elif kind == b"moof":
                self.pending = box
                self.started = time.monotonic()
            elif kind == b"mdat" and self.pending and self.initialized:
                fragments.append((self.started, self.pending + box))
                self.pending = b""
        return fragments
