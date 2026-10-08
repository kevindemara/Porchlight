"""Generate a public-safe contract without starting services or creating runtime data."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))
from porchlight.app import create_app  # noqa: E402

target = Path(__file__).resolve().parents[1] / "apps/web/openapi.json"
target.write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")
print("Exported OpenAPI contract")
