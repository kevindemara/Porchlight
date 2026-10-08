"""Synthetic search interpretation through native local-only Ollama; no footage."""

import asyncio
import json
import time
from datetime import UTC, datetime

from porchlight.ai.ollama import Ollama
from porchlight.config import Config
from porchlight.search import SEARCH_PROMPT, SEARCH_SCHEMA, validate_intent


async def check() -> bool:
    ollama = Ollama(Config())
    started = time.monotonic()
    try:
        now = datetime.now(UTC)
        content = await ollama.structured_text(
            "qwen3.8-27b-local:latest",
            SEARCH_SCHEMA,
            SEARCH_PROMPT,
            {
                "query": "black vehicles yesterday evening",
                "now": now.isoformat(),
                "timezone": "America/Toronto",
                "cameras": [],
            },
        )
        result = validate_intent(content, [], "America/Toronto", now)
        passed = (
            result.filters.categories == ["vehicle"]
            and result.filters.color == "black"
            and result.filters.daypart == "evening"
            and not result.needs_clarification
        )
        print(
            json.dumps(
                {
                    "passed": passed,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "categories": result.filters.categories,
                    "color": result.filters.color,
                    "daypart": result.filters.daypart,
                    "cloud_disabled": await ollama.cloud_disabled(),
                    "uses_synthetic_text_only": True,
                }
            )
        )
        return passed
    finally:
        await ollama.close()


if __name__ == "__main__":
    try:
        passed = asyncio.run(check())
    except Exception:
        print(json.dumps({"passed": False, "safe_code": "LOCAL_SEARCH_TEST_FAILED"}))
        raise SystemExit(1) from None
    raise SystemExit(0 if passed else 1)
