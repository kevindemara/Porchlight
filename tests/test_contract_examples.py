import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "example,schema",
    [
        ("event-analysis", "event-analysis"),
        ("event-analysis-infrared", "event-analysis"),
        ("notification-rule", "notification-rule"),
        ("search-query", "search-query"),
        ("daily-digest", "daily-digest"),
    ],
)
def test_supplied_examples_match_contracts(example: str, schema: str) -> None:
    validator = Draft202012Validator(
        json.loads((ROOT / f"schemas/{schema}.schema.json").read_text()),
        format_checker=FormatChecker(),
    )
    data = json.loads((ROOT / f"examples/{example}.example.json").read_text())
    validator.validate(data)
    validator.validate({**data})
    with pytest.raises(ValidationError):
        validator.validate({**data, "unknown_field": "must reject"})
