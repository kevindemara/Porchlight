from dataclasses import dataclass
from typing import Literal

from porchlight.api.contracts import ApiError

Workload = Literal["light", "balanced"]
WORKLOAD_VERSION = "workload-v1"


@dataclass(frozen=True)
class Preset:
    frames: int
    image_edge: int
    context: int
    output_tokens: int = 1800


PRESETS = {"light": Preset(3, 640, 4096), "balanced": Preset(6, 960, 8192)}


def preset(name: Workload) -> Preset:
    if name not in PRESETS:
        raise ApiError(422, "AI_WORKLOAD_REQUIRED", "Choose a supported local AI workload.")
    return PRESETS[name]
