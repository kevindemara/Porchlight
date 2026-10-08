# 06 · Ollama and the visual AI pipeline

## Design intent

Describe what is visibly supported in newly available recordings, not what a language model imagines probably happened. Use the existing local Ollama installation. A text/code model is not presumed to accept images. Ollama documents image inputs and JSON-schema-constrained responses; runtime support must still be tested for the chosen model/version. [A1–A3](15_SOURCES_AND_VERSIONING.md#a1)

## Discovery before installation

Query the configured loopback endpoint for version and installed models, inspect model details/capabilities where available, and run a small synthetic image test. Record exact model name, digest, quantization, Ollama version, and measured resources. Some old runtimes may not expose a capability field; a guarded image smoke test is then necessary. Do not use a successful text-only response as proof of vision.

Use a local model already present if it passes the tests. If a download is needed, show size/source and require an explicit user action. Do not replace existing models or change the model storage path.

Candidate baseline: `qwen3-vl:8b`; lighter alternative: `qwen3-vl:4b`; optional current comparison: `gemma4:12b`. The reviewed 8B Qwen tag listed a 6.1 GB Q4_K_M artifact, but file size is NOT total VRAM use. These are benchmark candidates, not an assertion of best accuracy or guaranteed fit on the user's 16 GB GPU. [A4–A5](15_SOURCES_AND_VERSIONING.md#a4)

## Strict local-only enforcement

Restrict the AI endpoint to an explicit loopback host/port allowlist. Do not accept arbitrary browser-supplied model URLs. Disallow cloud aliases and remote-backed models using runtime metadata/capability inspection plus a verified local-only server configuration; a `-cloud` name check alone is insufficient. An alias can conceal a remote model.

Ollama documents `OLLAMA_NO_CLOUD=1` or its server setting to disable cloud features. This is a global setting on the user's existing service: explain it and require approval before changing/restarting anything. Never silently alter their other workflows. [A6](15_SOURCES_AND_VERSIONING.md#a6) If strict local-only operation cannot be established, pause private-image analysis and present the issue. Test with synthetic imagery first.

No internet tool, function calling, web search, agent loop, or external image fetch in the analysis worker. Do not send audio, credentials, camera URLs, account metadata, geolocation, or entire original clips to the model. The backend sends only selected local images and minimal context.

## Frame extraction

After validating the file, use ffprobe to determine duration, image dimensions, rotation and codec. Decode with the installed FFmpeg using argument arrays, no shell interpolation, time/resource limits, and local-file-only inputs.

Initial preset: up to 6 chronological frames, long edge up to 960 px, overall request-image budget 8 MiB, one model job at a time, request timeout 90 seconds, context target 8192 tokens where supported. These are app tuning defaults, not universal model requirements. Adapt them only through measured presets.

Sample across the full duration, retaining start/end context where useful. Prefer additional visible-change frames rather than six near-identical frames. Deduplicate exact/near-exact samples and preserve original timestamps. Record each `frame_id`, offset_ms, SHA-256, extraction version, masking policy, and relationship to the source event. More evidence is not always better if small subjects become unreadable.

The default API path sends an ordered image array and a matching textual frame index through Ollama's native chat endpoint. It does **not** upload an MP4 to a fictional video endpoint. A labelled storyboard is an optional model-specific alternative that must be benchmarked; preserve source frame IDs either way. [A1](15_SOURCES_AND_VERSIONING.md#a1)

Privacy masks can be applied before inference and thumbnail creation. Clearly distinguish masking AI input/derivatives from removing pixels from the original archive; the latter requires a separately selected export/storage policy. Default audio analysis is off.

## Analysis contract

Use `schemas/event-analysis.schema.json` and `prompts/VISION_SYSTEM.md`. `examples/event-analysis.example.json` is synthetic contract data, not a real camera result. Send the schema through `format`, set `stream: false`, and validate the returned JSON server-side. Model parameter support varies; inspect runtime metadata before setting optional thinking flags. Do not blindly assume `think: false` works for every model. [A2–A3](15_SOURCES_AND_VERSIONING.md#a2)

The model returns observation mode, scene visibility, a suggested summary, entities, actions, direction, frame references, and uncertainty. It returns no executable command, remote URL, calibrated confidence score, or authoritative alarm decision.

Store a versioned analysis revision with model digest, prompt/schema versions, frame hashes, duration metrics and validation status. Keep the original observation immutable. User corrections are separate fields and can improve search/rules without silently rewriting history or fine-tuning a model.

## Semantic validators and safe summaries

JSON validity does not prove visual truth. Add deterministic checks:

- Every evidence ID must be among actual submitted frames and in chronological order where order matters.
- `single_image` cannot support a temporal direction/passing/approach/departure claim. Two identical images with different timestamps are not adequate motion evidence.
- IR/monochrome or uncertain visibility means `color=null`; do not infer “white” from a bright object under IR. Also remove that colour from the displayed summary.
- If temporal evidence is insufficient, downgrade to “vehicle visible” instead of claiming it drove by.
- “Delivery” requires visible placement/transition, not merely a person and a package in one image. The default summary may say “A person is visible near a package.”
- Unknown object categories/directions remain unknown. Never add make/model, identity, intent, protected attributes, or a precise speed.
- A set of sampled frames cannot establish that nothing happened between samples or outside the clip. Avoid “never entered” or “nobody else arrived.”

Generate the notification sentence from validated fields using a deterministic renderer initially. Keep the model's free-text suggested summary as a reviewable interpretation, not an unchecked push payload. For example, validated car + white + passing + left-to-right produces “A white car moves from left to right.” A night clip may produce “A vehicle is visible; colour is unclear.”

These safeguards reduce some failure modes, but do not certify the model is correct. Label descriptions as AI-generated and attach the original clip. Do not display a made-up “97% confidence” based on model self-report.

## Failure and workload policy

One bounded corrective retry for malformed output; subsequent failures become `analysis_failed`, not a never-ending loop. Hardware/timeout failures retry through the durable queue with backoff. If Ollama is unavailable, preserve the clip and optionally send “New recorded activity; AI analysis unavailable.”

Priority order: fresh event jobs, explicitly requested review, then historical backfill/digests. Bound backlog size and age; retain raw events when analysis is skipped. No notification storms when processing old history. Expose time waiting versus time generating. Keep a pause-AI toggle that does not pause recording ingestion.

Use short per-request keep-alive initially (for example 60 seconds); a longer warm-model preset is opt-in. Do not call stop/unload on the owner's unrelated models. Query running models and GPU resources when available, warn about contention, and benchmark while the PC is under ordinary workload. The application cannot guarantee that Ollama's own scheduler will never evict another model.

## Search and daily summaries

Full-text and typed filters work without AI. Natural-language search produces `schemas/search-query.schema.json`: bounded categories/colour/camera/time/query fields. Application code resolves relative dates in the owner's timezone, validates bounds, and executes parameterized queries. Never execute model-generated SQL or arbitrary expressions.

For daily digests, supply only saved validated observations, computed counts and event IDs. The model summarizes that dataset and cannot invent missed events. Include coverage gaps, failed analyses and relevant event links. Use `prompts/DAILY_DIGEST_SYSTEM.md`; keep metadata local. Embedding-based search is a later optional enhancement, not a mandatory model/database in the first build.

## Evaluation gate

Use owner-approved clips stored outside source: daylight white/dark vehicles, IR vehicles, pedestrians, animals, packages, rain/shadows, empty scenes and blurred/occluded subjects. Compare supported-claim precision, important-event misses, unknown rate, latency and GPU load. Keep a holdout set. A schema-valid result is not a visual-accuracy score. Choose the model/preset from this evaluation rather than a leaderboard claim.

## Implemented workload and review policy · 2026-10-07

Vision prompt 1.1 explicitly maps each permitted subtype to its category; person/other/unknown require a null subtype. Validation remains authoritative. Queued analysis freezes prompt-contract, extraction and workload versions in its payload and durable key. An incompatible app update blocks that job before images enter inference with `ANALYSIS_CONTRACT_CHANGED`; the owner can request a new analysis under the current contract. Earlier accepted revisions and source footage remain available. Current-version legacy keys without the newer explicit payload fields remain runnable.

`workload-v1` has Balanced (6 samples, 960 px, 8192 context) and Light (3 samples, 640 px, 4096 context); both cap output at 1800 tokens and all images at 8 MiB. The `uniform-up-to-six-local-change-v3` sampler spaces candidates across the clip including near its end, retains localized motion differences and deduplicates near-identical images. The selected preset is frozen in the job and input fingerprint; it also appears in revision metadata. Existing queued jobs without a preset use Balanced.

Malformed output stores only a static allowlisted validation reason (JSON/schema/evidence/contract), never raw response/exception prose. Diagnostics aggregate these reasons. Historical provenance prohibits automatic analysis and notifications permanently; explicit manual review is allowed.

The latest native Balanced run accepted five frames in 43.66 seconds (43.80 seconds overall), describing a person approaching and a black car. Light's one-attempt probe rejected its output in 45.88 seconds. These are runtime/schema/evidence results, not visual accuracy or GPU-fit scores; the saved preset remains Balanced and automatic AI is off. The Light failure preceded the new safe-reason classifier, so its precise validation cause is unknown.

Evidence images are reconstructed with the identical native decoder settings and must match each accepted SHA-256 before delivery. Requests name an existing event/revision/frame; no arbitrary timestamp/file path is accepted. The authenticated, no-store endpoint has two decoder slots, at most twelve pending requests and a 20-second deadline. It writes no derivative copies. Older extraction revisions retain sampled-time review; mismatched decoder output is unavailable rather than substituted.
