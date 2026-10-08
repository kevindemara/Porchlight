# First prompt for Codex

Open the extracted project folder in your **local** Codex environment and paste everything in the block below. Local execution is needed for testing the existing Ollama service and, later, the owner's Blink connection. No Blink password belongs in the prompt.

```text
Build Porchlight from the specification package in this project folder. This is an implementation request, not a request for another plan or a static UI mockup.

Start by reading AGENTS.md, README.md, BUILD_STATUS.md, docs/02_BLINK_COMPATIBILITY_AND_NO_SUBSCRIPTION.md, docs/03_ARCHITECTURE.md, docs/04_REPOSITORY_RESEARCH_AND_LICENSES.md, and docs/12_IMPLEMENTATION_PLAN.md. Then read the documents, schemas, examples, and prompts needed for each milestone.

The target is my existing Windows Lenovo Legion PC with Ollama already installed. Verify the machine, installed tools, actual Ollama endpoint, model capabilities, and available resources. Do not reinstall Ollama, move its model directory, delete/unload my unrelated models, enable cloud inference, or expose it on the network. Use an existing suitable LOCAL vision model when one is available. A coding model must not be assumed to accept images. If none is suitable, build the model-selection screen and show the precise optional download command instead of silently downloading gigabytes.

Implement the Windows-native FastAPI + SQLite + React/TypeScript/Vite architecture. Build the frontend into the backend's same-origin static deployment. No Home Assistant, Frigate, Homebridge, paid API, hosted database, or Docker requirement for the core application.

Implement milestones M0 through M6 in dependency order, with tests and usable vertical slices. The central path is authenticated Blink access -> enumerate all newly available recordings -> durable local download -> timestamped frame extraction -> local Ollama analysis -> evidence-checked summary -> rule evaluation -> event timeline and notifications.

Treat no-subscription recording access as a hard validation gate. Discover my camera and Sync Module capabilities through setup; do not assume USB/local storage works just because the official Blink app supports it. Separately implement cloud, Sync Module local-storage, and manual-import providers. If a camera cannot supply recordings without a plan, explain the specific missing capability. Never purchase/cancel a plan, bypass an entitlement, invent an API endpoint, or call imported demo clips proof of Blink support.

Build a local password/verification-code setup flow. Never request Blink credentials in this chat or put them in source, logs, screenshots, command-line arguments, or .env files. Preserve existing official-app functionality and never disarm a real system just to run an automated test.

Use the provided JSON schemas and prompt templates, then add semantic validators and tests. Preserve raw events if AI fails. Do not infer a vehicle's colour from infrared footage or say it drove past from a single still image. Make uncertain and failed analysis states visible.

Build the original, polished mobile-friendly UI in docs/08_UI_UX_SPECIFICATION.md, not a clone of Blink's assets. Implement honest capability badges, recording timestamps, playback, filters, search, favourites, retention, diagnostics, and notification setup. Phone background delivery needs a real notification transport and testing; a web socket or open-tab toast alone is not push.

Keep live view behind a disabled experimental flag until M7 proves it on my actual camera. Never display a frozen frame or replayed clip as LIVE. Two-way audio and continuous recording are not assumed features.

Verify current upstream interfaces/licences, pin the versions actually tested, and isolate blinkpy in its adapter. Do not copy unlicensed blinkbridge code or transplant GPL Homebridge code into an assumed permissive app. Implement product ideas independently where appropriate.

When login, hardware, or a phone test requires me, continue all independent code/tests using labelled fixtures and mark the relevant validation NOT RUN. Do not stop at a pretty mockup, and do not claim production readiness from mocks. Keep BUILD_STATUS.md and the hardware validation report updated with actual evidence.

Begin by inspecting the project and local environment, then implement M0 and the first runnable M1/M2 vertical slice. Continue through the milestones as the session permits. At handoff, give the exact launch/test commands, passing/failing tests, remaining real-device checks, and the next runnable task.
```

## Follow-on prompts

Use [prompts/CODEX_CONTINUE.md](prompts/CODEX_CONTINUE.md) to resume, [prompts/CODEX_AUDIT.md](prompts/CODEX_AUDIT.md) before calling it ready, and [prompts/CODEX_UI_POLISH.md](prompts/CODEX_UI_POLISH.md) after the real data flow works.

## Important

The AI models in Porchlight analyze footage locally. That is separate from whichever coding model you choose for Codex. Using Codex does not require embedding a Codex/OpenAI API into Porchlight. The runtime must contain no hidden cloud AI dependency.
