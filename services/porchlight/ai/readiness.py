"""Bounded read-only hardware hints. A hint is never permission or a fit guarantee."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from typing import Literal

from porchlight.api.contracts import AiReadiness

GIB = 1024**3


def memory_bytes() -> int | None:
    try:
        if os.name == "nt":

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
                    (name, ctypes.c_uint64)
                    for name in (
                        "total",
                        "available",
                        "page_total",
                        "page_available",
                        "virtual_total",
                        "virtual_available",
                        "extended",
                    )
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return int(status.total)
        sysconf = getattr(os, "sysconf", None)
        if sysconf:
            return int(sysconf("SC_PHYS_PAGES")) * int(sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, AttributeError):
        pass
    return None


def gpu_bytes() -> int | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None  # Other GPUs may work; absence is not a failed compatibility test.
    try:
        result = subprocess.run(
            [executable, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        values = [int(line.strip()) for line in result.stdout.splitlines()[:16]]
        if values and all(0 < value < 1024 * 1024 for value in values):
            return max(values) * 1024**2  # Do not add memory across separate GPUs.
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def recommend(ram: int | None, gpu: int | None, threads: int | None) -> AiReadiness:
    tier: Literal["unknown", "skip", "cpu", "light", "balanced"] = "unknown"
    model: Literal["qwen3-vl:4b", "qwen3-vl:8b"] | None = None
    workload: Literal["light", "balanced"] = "light"
    message = "Hardware information is incomplete. Keep AI off, or test an existing local model."
    # Rounded vendor RAM sizes can be slightly below the nominal capacity.
    # These conservative Porchlight heuristics are not Ollama minimum requirements.
    if ram is not None:
        if ram < 15 * GIB:
            tier = "skip"
            message = "Start without AI to leave memory for Windows and the archive."
        elif gpu is not None and gpu >= 12 * GIB and ram >= 23 * GIB:
            tier, model, workload = "balanced", "qwen3-vl:8b", "balanced"
            message = "Try the balanced candidate, then measure the local image test."
        elif gpu is not None and gpu >= 7 * GIB:
            tier, model = "light", "qwen3-vl:4b"
            message = "Try the smaller candidate with Light sampling, then run the image test."
        else:
            tier, model = "cpu", "qwen3-vl:4b"
            message = (
                "A small model may work slowly on CPU or another supported GPU. "
                "Skipping AI is a good starting choice."
            )
    return AiReadiness(
        ram_bytes=ram,
        gpu_memory_bytes=gpu,
        cpu_threads=threads,
        recommendation=tier,
        suggested_model=model,
        suggested_workload=workload,
        message=message,
    )


def inspect_machine() -> AiReadiness:
    return recommend(memory_bytes(), gpu_bytes(), os.cpu_count())
