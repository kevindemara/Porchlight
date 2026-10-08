from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from porchlight.ai.frames import Frame, similar
from porchlight.api.contracts import ApiError
from porchlight.config import ROOT

SCHEMA = json.loads((ROOT / "schemas/event-analysis.schema.json").read_text(encoding="utf-8"))
PROMPT = (
    (ROOT / "prompts/VISION_SYSTEM.md")
    .read_text(encoding="utf-8")
    .split("```text\n")[1]
    .split("```")[0]
)
CONTRACT_DIGEST = hashlib.sha256((PROMPT + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()
SUBTYPES = {
    "vehicle": {"car", "truck", "van", "bus", "motorcycle", "bicycle"},
    "animal": {"dog", "cat", "bird"},
    "package": {"box", "envelope"},
}
TEMPORAL = {
    "moving",
    "passing",
    "approaching",
    "departing",
    "stopping",
    "parked",
    "placing_object",
    "picking_up_object",
}

VALIDATION_REASONS = {
    "json_invalid",
    "response_too_large",
    "duplicate_entity",
    "evidence_order",
    "subtype_mismatch",
    "frame_reference",
    "contract_invalid",
    *{
        f"schema_{keyword}"
        for keyword in (
            "enum",
            "type",
            "required",
            "additionalProperties",
            "uniqueItems",
            "maxItems",
            "maxLength",
            "pattern",
        )
    },
}


class ObservationError(ApiError):
    def __init__(self, reason: str):
        super().__init__(
            422,
            "ANALYSIS_INVALID",
            "The model response did not match the visual evidence contract.",
        )
        self.safe_reason = reason if reason in VALIDATION_REASONS else "contract_invalid"


def validation_reason(error: Exception) -> str:
    if isinstance(error, json.JSONDecodeError):
        return "json_invalid"
    if isinstance(error, ValidationError):
        return f"schema_{error.validator}"
    if isinstance(error, KeyError):
        return "frame_reference"
    return {
        "Too large": "response_too_large",
        "Duplicate entity": "duplicate_entity",
        "Out of order evidence": "evidence_order",
        "Inconsistent subtype": "subtype_mismatch",
    }.get(str(error), "contract_invalid")


def validate_observation(content: str, frames: list[Frame]) -> tuple[dict[str, Any], str]:
    try:
        if len(content.encode()) > 64 * 1024:
            raise ValueError("Too large")
        observation: dict[str, Any] = json.loads(content)
        # Repeating an allowed action adds no meaning. Canonicalize exact enum repeats;
        # malformed types, unknown values and all evidence requirements still fail validation.
        if isinstance(observation, dict) and isinstance(observation.get("entities"), list):
            allowed_actions = set(
                SCHEMA["properties"]["entities"]["items"]["properties"]["actions"]["items"]["enum"]
            )
            for entity in observation["entities"]:
                if not isinstance(entity, dict):
                    continue
                actions = entity.get("actions")
                if isinstance(actions, list) and all(
                    isinstance(action, str) and action in allowed_actions for action in actions
                ):
                    entity["actions"] = list(dict.fromkeys(actions))
        Draft202012Validator(SCHEMA).validate(observation)
        lookup = {frame.id: frame for frame in frames}
        seen: set[str] = set()
        limitations: list[str] = []
        descriptions: list[str] = []
        observation["observation_mode"] = "video_frames" if len(frames) > 1 else "single_image"
        if all(frame.monochrome for frame in frames):
            observation["scene_visibility"] = "infrared_monochrome"
        for entity in observation["entities"]:
            if entity["entity_id"] in seen:
                raise ValueError("Duplicate entity")
            seen.add(entity["entity_id"])
            references = [lookup[frame_id] for frame_id in entity["evidence_frame_ids"]]
            if [f.offset_ms for f in references] != sorted(f.offset_ms for f in references):
                raise ValueError("Out of order evidence")
            temporal = len(references) >= 2 and any(
                not similar(a.signature, b.signature)
                for a in references
                for b in references
                if a.offset_ms < b.offset_ms
            )
            if not temporal:
                entity["actions"] = ["visible"]
                entity["direction"] = "unknown"
                limitations.append("A still or repeated image cannot establish movement.")
            elif not any(action in TEMPORAL for action in entity["actions"]):
                entity["direction"] = "unknown"
            category = entity["category"]
            subtype = entity["subtype"]
            if subtype and subtype not in SUBTYPES.get(category, set()):
                raise ValueError("Inconsistent subtype")
            if (
                category in {"person", "other", "unknown"}
                or entity["color_evidence"] != "visible"
                or observation["scene_visibility"] not in {"daylight_color", "low_light_color"}
                or any(frame.monochrome for frame in references)
            ):
                if entity["color"] is not None:
                    limitations.append("Colour was omitted where the evidence is insufficient.")
                entity["color"], entity["color_evidence"] = None, "uncertain"
            if category in {"unknown", "other"}:
                label = "object"
            else:
                label = subtype or category
            if entity["color"] and entity["color"] != "other":
                label = f"{entity['color']} {label}"
            prefix = "An" if label[0].lower() in "aeiou" else "A"
            actions = entity["actions"]
            verb = (
                "passes"
                if "passing" in actions
                else "approaches"
                if "approaching" in actions
                else "moves away"
                if "departing" in actions
                else "moves"
                if "moving" in actions
                else "is visible"
            )
            direction = (
                {
                    "left_to_right": " from left to right",
                    "right_to_left": " from right to left",
                    "toward_camera": " toward the camera",
                    "away_from_camera": " away from the camera",
                }.get(entity["direction"], "")
                if verb in {"moves", "passes"}
                else ""
            )
            descriptions.append(f"{prefix} {label} {verb}{direction}.")
        if observation["uncertainty"]:
            limitations.append("The model reported uncertainty about the sampled images.")
        # Never persist/display unchecked prose, image instructions, identities or URLs.
        summary = (
            " ".join(descriptions[:3]) or "The sampled images could not be reliably described."
        )
        observation["summary_suggestion"] = summary
        observation["uncertainty"] = list(dict.fromkeys(limitations))[:8]
        return observation, summary
    except (ValueError, TypeError, KeyError, ValidationError) as exc:
        raise ObservationError(validation_reason(exc)) from exc
