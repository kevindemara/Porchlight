# Package validation report

Prepared on **October 6, 2026**. These results describe the original documentation package only, before application development. Current runtime validation is in [BUILD_STATUS.md](BUILD_STATUS.md).

## Checks performed

- All JSON files parse successfully.
- All **4 JSON Schema contracts** pass Draft 2020-12 schema validation.
- All **5 schema-backed synthetic examples** validate with format checking. The separate settings example is syntax-checked; its application settings model remains for Codex to implement.
- **14 negative contract cases** were rejected as expected: unknown fields, invalid categories/colours, malformed or duplicate frame references, excessive text, SQL-shaped extra fields, invalid IDs/timestamps, negative cooldown, invalid quiet hours, historical notification enablement, missing channels and unknown digest fields.
- Relative Markdown file links and source anchors resolve; Markdown code fences are balanced; fenced JSON examples parse.
- `AGENTS.md` is below the documented default 32 KiB instruction-file budget.
- All expected documents, prompts, schemas, examples and the preflight script are present and nonempty.

The final ZIP is integrity-tested and its extracted contents match the source file hashes during assembly.

## Explicitly not performed

No application was implemented or launched. No Blink account/camera/Sync Module was accessed. No subscription-free recording retrieval was tested. No Ollama model was run or benchmarked. No phone notification was sent. No Windows startup/vault/FFmpeg integration was executed. **The PowerShell preflight script was written and reviewed but not executed on Windows; PowerShell was not available in the assembly environment.**

JSON Schema tests are not an AI visual-accuracy or semantic-validation test. An infrared colour assertion can still fit the shape of the schema; the later application's evidence/visibility validator must reject it. The supplied examples are invented, not camera observations.

See [BUILD_STATUS.md](BUILD_STATUS.md) for the current implementation and measured checks and [the test plan](docs/13_TESTS_AND_ACCEPTANCE.md) for future validation requirements.
