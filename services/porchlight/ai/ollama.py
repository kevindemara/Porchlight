from __future__ import annotations

import asyncio
import base64
import json
import struct
import time
import zlib
from typing import Any

import httpx

from porchlight.ai.frames import Frame
from porchlight.ai.observations import PROMPT, SCHEMA
from porchlight.ai.workloads import Workload, preset
from porchlight.api.contracts import AiResources, ApiError, ModelList, ModelTestResult, ModelView
from porchlight.config import Config


def synthetic_image() -> str:
    # A generated red block on the left and blue block on the right; no personal footage.
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    width, height = 160, 96
    rows = b"".join(b"\x00" + b"\xe6\x19\x19" * 80 + b"\x19\x19\xe6" * 80 for _ in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode()


class Ollama:
    def __init__(self, config: Config, transport: httpx.AsyncBaseTransport | None = None):
        self.client = httpx.AsyncClient(
            base_url=config.ollama_url,
            timeout=120,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
        self.inference_lock = asyncio.Lock()

    async def close(self) -> None:
        await self.client.aclose()

    async def request(
        self, method: str, route: str, body: dict[str, Any] | None = None, *, timeout: float = 10
    ) -> dict[str, Any]:
        try:
            async with self.client.stream(method, route, json=body, timeout=timeout) as response:
                response.raise_for_status()
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2 * 1024**2:
                        raise ValueError("Model response too large")
            data: Any = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Unexpected model response")
            return dict(data)
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError(
                503,
                "OLLAMA_UNAVAILABLE",
                "Ollama did not respond successfully. Check your local AI service.",
                True,
            ) from exc

    async def cloud_disabled(self) -> bool:
        try:
            data = await self.request("GET", "/api/status")
            return isinstance(data.get("cloud"), dict) and data["cloud"].get("disabled") is True
        except ApiError:
            return False

    async def resources(self, selected: str | None) -> AiResources:
        """Read shared-service occupancy without changing or unloading any model."""
        try:
            data = await self.request("GET", "/api/ps", timeout=3)
            rows = data.get("models")
            if not isinstance(rows, list) or len(rows) > 40:
                raise ValueError("Invalid occupancy")
            sizes, others, selected_loaded = [], 0, False
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("name"), str):
                    raise ValueError("Invalid loaded model")
                size = row.get("size_vram")
                if type(size) is not int or not 0 <= size < 2**50:
                    raise ValueError("Invalid memory size")
                sizes.append(size)
                if selected and row["name"] == selected:
                    selected_loaded = True
                else:
                    others += 1
            return AiResources(
                available=True,
                loaded_models=len(rows),
                other_loaded_models=others,
                loaded_vram_bytes=sum(sizes),
                selected_loaded=selected_loaded,
                inference_busy=self.inference_lock.locked(),
                contention_possible=others > 0,
            )
        except (ApiError, ValueError):
            return AiResources(
                available=False,
                loaded_models=0,
                other_loaded_models=0,
                loaded_vram_bytes=0,
                selected_loaded=False,
                inference_busy=self.inference_lock.locked(),
                contention_possible=False,
            )

    async def private_model(self, name: str | None) -> ModelView:
        if not await self.cloud_disabled():
            raise ApiError(
                409,
                "LOCAL_ONLY_REQUIRED",
                "Ollama must confirm cloud features are disabled before private clip analysis.",
            )
        inventory = await self.models()
        selected = next((m for m in inventory.models if m.name == name), None)
        if not selected or not selected.local or not selected.vision or not selected.digest:
            raise ApiError(409, "VISION_MODEL_REQUIRED", "Select and test a local vision model.")
        return selected

    async def analyze(
        self, model: ModelView, frames: list[Frame], workload: Workload = "balanced"
    ) -> str:
        policy = preset(workload)
        async with self.inference_lock:
            current = await self.private_model(model.name)
            if current.digest != model.digest:
                raise ApiError(409, "MODEL_CHANGED", "The model changed. Test it again first.")
            detail = await self.request("POST", "/api/show", {"model": model.name})
            # Recheck the running server immediately before sending private images.
            if not await self.cloud_disabled():
                raise ApiError(409, "LOCAL_ONLY_REQUIRED", "Ollama cloud features are enabled.")
            data = await self.request(
                "POST",
                "/api/chat",
                {
                    "model": model.name,
                    "stream": False,
                    "format": SCHEMA,
                    "keep_alive": "60s",
                    **({"think": False} if "thinking" in detail.get("capabilities", []) else {}),
                    "messages": [
                        {"role": "system", "content": PROMPT},
                        {
                            "role": "user",
                            "content": (
                                "Observe only these sampled frames in chronological order. "
                                "Frame index: " + json.dumps([frame.evidence() for frame in frames])
                            ),
                            "images": [frame.encoded() for frame in frames],
                        },
                    ],
                    "options": {
                        "num_ctx": policy.context,
                        "num_predict": policy.output_tokens,
                        "temperature": 0,
                    },
                },
                timeout=90,
            )
            message = data.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ApiError(422, "ANALYSIS_INVALID", "The model response was incomplete.")
            return str(message["content"])

    async def models(self) -> ModelList:
        version = await self.request("GET", "/api/version")
        tags = await self.request("GET", "/api/tags")
        models: list[ModelView] = []
        for item in tags.get("models", [])[:40]:
            name = str(item.get("name", ""))
            if not name:
                continue
            detail = await self.request("POST", "/api/show", {"model": name})
            vision = "vision" in detail.get("capabilities", [])
            # Metadata is mandatory; alias names alone cannot establish local execution.
            local = bool(
                detail.get("details", {}).get("format") == "gguf"
                and not detail.get("remote_host")
                and not detail.get("remote_model")
                and "cloud" not in detail.get("capabilities", [])
            )
            models.append(
                ModelView(
                    name=name,
                    digest=str(item.get("digest", "")),
                    size_bytes=int(item.get("size", 0)),
                    vision=vision,
                    local=local,
                    reason=(
                        "Local vision model"
                        if vision and local
                        else "Image analysis requires a local vision model"
                    ),
                )
            )
        return ModelList(version=str(version.get("version", "unknown")), models=models)

    async def structured_text(
        self, name: str | None, schema: dict[str, Any], prompt: str, data: dict[str, Any]
    ) -> str:
        async with self.inference_lock:
            model = await self.private_model(name)
            detail = await self.request("POST", "/api/show", {"model": model.name})
            if not await self.cloud_disabled():
                raise ApiError(409, "LOCAL_ONLY_REQUIRED", "Ollama cloud features are enabled.")
            response = await self.request(
                "POST",
                "/api/chat",
                {
                    "model": model.name,
                    "stream": False,
                    "format": schema,
                    "keep_alive": "60s",
                    **({"think": False} if "thinking" in detail.get("capabilities", []) else {}),
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": json.dumps(data)},
                    ],
                    "options": {"num_ctx": 8192, "num_predict": 800, "temperature": 0},
                },
                timeout=90,
            )
            message = response.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ApiError(422, "INTERPRETATION_INVALID", "Choose search filters manually.")
            return str(message["content"])

    async def smoke_test(self, model: str) -> ModelTestResult:
        if self.inference_lock.locked():
            raise ApiError(
                409, "AI_BUSY", "A model test is already running. Wait for it to finish."
            )
        async with self.inference_lock:
            inventory = await self.models()
            selected = next((m for m in inventory.models if m.name == model), None)
            if not selected or not selected.vision or not selected.local:
                raise ApiError(
                    422, "VISION_MODEL_REQUIRED", "Choose an installed local vision model."
                )
            schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {"left": {"type": "string"}, "right": {"type": "string"}},
                "required": ["left", "right"],
            }
            started = time.monotonic()
            detail = await self.request("POST", "/api/show", {"model": model})
            thinking_options = (
                {"think": False} if "thinking" in detail.get("capabilities", []) else {}
            )
            data = await self.request(
                "POST",
                "/api/chat",
                {
                    **thinking_options,
                    "model": model,
                    "stream": False,
                    "format": schema,
                    "keep_alive": "60s",
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Inspect the attached image. Return the main color "
                                "of its left and right halves."
                            ),
                            "images": [synthetic_image()],
                        }
                    ],
                    "options": {"num_ctx": 4096, "num_predict": 100, "temperature": 0},
                },
                timeout=120,
            )
            try:
                answer = json.loads(data.get("message", {}).get("content", ""))
                passed = (
                    set(answer) == {"left", "right"}
                    and answer["left"].lower().strip() == "red"
                    and answer["right"].lower().strip() == "blue"
                )
            except (ValueError, TypeError, AttributeError):
                passed = False
            return ModelTestResult(
                passed=passed,
                model=model,
                digest=selected.digest,
                elapsed_seconds=round(time.monotonic() - started, 2),
                message=(
                    "Synthetic image and structured response passed. Camera accuracy is untested."
                    if passed
                    else "The synthetic image test did not pass."
                ),
            )
