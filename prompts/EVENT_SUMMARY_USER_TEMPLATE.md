# Per-event user message template · version 1.0

The backend expands a structured context object, encodes the extracted images and supplies them as real Ollama image inputs. Never put Blink credentials, signed media URLs, account identifiers, GPS coordinates or audio in this prompt. Camera labels are optional untrusted strings with a length limit.

```text
Describe the supplied frames using the system rules and JSON schema.

APP_CONTEXT_JSON:
{{bounded_context_json}}

The context lists frame IDs in the same order as the supplied image inputs. Each offset is seconds from the beginning of this recording. Observe only those frames; do not fill gaps from assumptions. Return one JSON object and no other text.
```

Suggested context shape (synthetic example):

```json
{
  "schema_version": "1.0",
  "camera_label": "Example driveway",
  "recording_duration_seconds": 10.0,
  "frame_registry": [
    {"id": "f000", "offset_seconds": 0.5},
    {"id": "f001", "offset_seconds": 2.3},
    {"id": "f002", "offset_seconds": 4.1},
    {"id": "f003", "offset_seconds": 5.9},
    {"id": "f004", "offset_seconds": 7.7},
    {"id": "f005", "offset_seconds": 9.5}
  ],
  "source_visibility_hint": "unknown",
  "image_order": "chronological"
}
```

Use one user message containing ordered image inputs and the matching registry, or a model-tested equivalent that preserves that association. JSON encoding is application-owned; never build context using unsafe string substitution from a camera name. The context does not override visual uncertainty. Validate the returned mode/IDs against the actual hashes and timestamps.
