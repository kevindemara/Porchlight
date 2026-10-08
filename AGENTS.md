# Porchlight engineering instructions

## Product and non-negotiables

Build the application described in `README.md` and `docs/`, not another planning document. This repository initially contains a specification package, not implemented application code. Preserve it, implement in small tested vertical slices, and keep `BUILD_STATUS.md` accurate.

- Local-first: use the existing native Ollama service. No paid AI API, cloud inference fallback, hosted database, required SaaS account, or required Blink subscription.
- A no-subscription claim requires evidence that NEW recordings can be retrieved under a verified eligible no-plan configuration. Keep entitlement unknown when it is unknown. Do not activate, cancel, or buy any subscription.
- Unofficial Blink access remains cloud-dependent. Do not advertise offline Blink operation or arbitrary 24/7 recording.
- Capability-gate live view, local-storage retrieval, manual recording, two-way audio, doorbell events, and model-specific controls. Never display an old thumbnail or replayed recording as live video.
- Use legitimate owner-authorized authentication. No CAPTCHA bypass, credential harvesting, paid-feature bypass, or private mobile push interception.
- Do not ask for credentials in chat. Build a local setup form, disable request-body logging on secrets routes, and use the OS-backed vault.
- Do not send private clips, frames, login tokens, or unredacted diagnostics to Codex/cloud tooling. Use synthetic fixtures in source and tests. Keep real test artifacts outside the repository.

## Read before implementing

Read `README.md`, `docs/02_BLINK_COMPATIBILITY_AND_NO_SUBSCRIPTION.md`, `docs/03_ARCHITECTURE.md`, `docs/04_REPOSITORY_RESEARCH_AND_LICENSES.md`, `docs/12_IMPLEMENTATION_PLAN.md`, and `BUILD_STATUS.md`. Read the milestone-specific contracts next. Do not assume the entire docs directory has been loaded automatically by Codex.

## Architecture constraints

One Windows-native Python/FastAPI application process with a persistent SQLite job queue, an account-scoped Blink actor, and background job loops. One Uvicorn worker in production; no reload in production. Build the React/TypeScript/Vite frontend as static assets served by the same origin. Keep SQLite and media off OneDrive/SMB paths. Ollama stays on loopback; the browser never calls it or Blink directly.

Only `services/porchlight/providers/blink/` may import `blinkpy`. Domain services consume our provider interface. Investigate the current stable dependency, record the tested exact version, and commit lockfiles. `blinkpy` 0.25.9 was the release displayed during research; this is a candidate, not a tested pin.

Do not combine entire Home Assistant, Frigate, or Homebridge applications. Reuse libraries through their APIs where appropriate, and implement our own product workflows. `blinkbridge` had no licence visible in the reviewed root: no code copying without verified permission. Homebridge Blink Security carries GPLv3 text: do not transplant it into an assumed permissively licensed codebase. See the licence ledger before reusing anything.

## Correctness

- Enumerate and reconcile ALL discoverable clips; never treat `camera.video_from_cache` as complete event history.
- Explicitly separate cloud clips, Sync Module local clips, manual imports, and demo fixtures.
- Stable source keys + SHA-256 + database uniqueness + transactional outbox; restart-safe jobs and bounded retries.
- Never advance discovery checkpoints past pages that were not durably recorded. Downloads may fail independently and retry later.
- Match controls to observed remote state. Use pending/failed/unknown states, not optimistic fake success.
- AI input is untrusted data. Images and text inside images are not instructions. No tools or network access for the vision inference.
- Schema validation is necessary but not proof of visual truth. Validate frame references, temporal evidence, colour visibility, and permitted claims.
- Owner-requested face recognition is opt-in, local, and limited to named SFace profiles reviewed against source clips. Never infer demographics or criminal intent. No automatic disarming or emergency actions based on AI.
- Raw event preservation must not depend on AI success. Unknown events remain visible; filtering is conservative and reversible.

## Defaults and security

Bind to `127.0.0.1:8765` until local admin setup is complete. Require local authentication, allowed Host/Origin checks, CSRF protection for state changes, and no credentials in localStorage. Protect media routes, including Range requests and experimental live segments. Do not register services, trust certificates, change firewall rules, disable sleep, install software, or download models without a specific local action/approval. Never expose Ollama publicly.

No automatic global Ollama reconfiguration or unloading of unrelated running models. Detect local vision capabilities and shared GPU contention. Cloud model aliases must be rejected using runtime metadata and local-only policy, not merely a name check.

## Workflow and testing

Use strict Python and TypeScript types, migrations, small modules, structured/redacted logging, and generated API types. Build testable adapters and explicitly labelled demo mode. Implement M0–M6 in order; M7 live-view work is optional and cannot block the reliable clip application.

At each milestone: execute relevant tests, inspect the UI at phone and desktop widths, fix failures, update status and decisions, then proceed. If real hardware or interactive login is unavailable, continue independent implementation but mark hardware checks NOT RUN. Do not claim success from mocked HTTP responses.

Create runnable `bootstrap.ps1`, `dev.ps1`, `start.ps1`, `stop.ps1`, `test.ps1`, `backup.ps1`, and `restore.ps1` as the implementation evolves. Commands documented as future outputs do not exist until implemented. Keep installers and services opt-in. Do not turn off tests or weaken security to obtain a passing result.

At every handoff state: files changed; exact commands executed and results; real versus simulated evidence; current milestone; blockers; next runnable step. Leave the repository in a resumable state. Never fabricate measured latency, accuracy, or device compatibility.
