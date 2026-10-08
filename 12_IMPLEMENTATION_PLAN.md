# 12 · Implementation plan

## Delivery model

Implement runnable vertical slices, not all screens followed by a late integration attempt. Each milestone ends with a working command, reproducible tests, an updated `BUILD_STATUS.md`, and evidence of what has and has not been exercised. Commit only public-safe code and synthetic fixtures. Version numbers in this package are research observations, not a lockfile.

The critical path is **M0 foundation → M1 real recording-access spike → M2 reliable archive → M3 local analysis → M4 finished workflows → M5 phone alerts → M6 operational hardening**. M7 live view is explicitly outside the subscription-free core release. Build a minimal UI in M0/M1; M4 is not the first time the owner can use the app.

Do not halt all development while waiting for a login or phone. Build and test independent components with clearly labelled fixtures. However, hardware-dependent gates stay NOT RUN/BLOCKED; passing mocks cannot turn them green.

## M0 · Repository, local environment and safe application shell

**Objective:** a real running backend and frontend with explicit configuration, first-run security and deterministic development setup.

Read AGENTS, architecture, security and Windows operations. Inspect the existing repository before creating files. Run or review the read-only preflight script. Inspect installed Python, Node, FFmpeg and Ollama without reinstalling or reconfiguring the owner's tools. Choose supported dependency versions, pin and lock them, and record the reason for any optional installation.

Create `services/porchlight/`, `apps/web/`, `tests/`, migrations and a repeatable local launcher. Use a Python virtual environment and the selected existing package manager; do not depend on pnpm being installed. Add lint/type/test scripts, `.gitignore`, configuration validation, structured redacted logging and a `THIRD_PARTY_NOTICES.md` ledger. Keep runtime data outside the source directory.

Build SQLite migrations, local owner setup/login, session security, a loopback-only first-run bootstrap, host/origin validation, CSRF controls, minimal `/health/live`, authenticated `/api/v1/health`, a real static frontend build and a visible setup-state screen. Separate developer health output from authenticated detailed diagnostics. Add a single-instance lock and graceful shutdown.

**Exit criteria:** clean-checkout setup and launch work; unauthorized requests cannot read footage/settings; no default credentials; a second worker cannot start duplicate polling; an empty app shows setup, not fake cameras; synthetic fixture mode is visibly labelled. Record Windows-specific items not exercised in another OS.

## M1 · Blink authentication and compatibility spike

**Objective:** prove the hardest external assumption before investing in advanced UI.

Inspect the actual pinned blinkpy interfaces and write `docs/BLINKPY_API_MAP.md` identifying version/commit, supported public calls, optional private bridge calls, auth serialization and tested recording paths. Own protocol method names are not claimed upstream functions. Implement `BlinkAdapter`, a deterministic fake, and separate cloud/local-storage recording providers. Map stable IDs, not display names.

Build the owner-facing local login/verification flow, an OS-protected credential store, encrypted session persistence, reconnect/re-auth states, redaction tests and one serialized account actor. Do not print passwords or verification codes. Do not use the developer's personal Blink account for tests.

Discover devices, networks, module type, storage/entitlement data where available, and explicit unknowns. Make a capability screen that differentiates advertised upstream support, observed API support and successfully verified operations. Implement conservative request scheduling, complete clip discovery, and one owner-approved recording download/playback.

**No-subscription hardware gate:** on a genuinely eligible source, verify three newly created distinct motion clips and a fourth after an app restart, with no active paid/trial recording entitlement. Document how that entitlement was established; owner confirmation may be necessary. Test automatic listing and downloading, not just manual access to the official app. Do not cancel a plan to manufacture this test.

**Exit criteria:** credentials never leave the intended Blink auth path/vault; at least the supported real recording path works when owner access is available; official-app operation is preserved; cloud/local/import/demo are distinguished; the report honestly says VERIFIED, UNVERIFIED or BLOCKED. An incompatible account can still use manual imports, but the product must not call it autonomous Blink monitoring.

## M2 · Durable recording ingestion and local archive

**Objective:** new available clips reliably become playable local events without duplication or loss caused by AI failures.

Implement paginated discovery and an overlap-based cursor per provider. Enumerate every available new clip; do not use a camera's latest cached video as history. Request manifests/prepared downloads with bounded retries. Validate expected media, HTTP redirects/hosts, byte limits and timestamps. Write to temporary files, hash/inspect, atomically promote and transactionally record the result. Recovery must handle crashes between these stages.

Implement durable jobs with leases, unique idempotency keys, a persisted outbox, retry classes/backoff, retention tombstones, camera reconciliation and storage-offline states. Download work and local AI work must not share a blocking failure boundary. Add a manual import flow with file validation and distinct provenance. A filename must never control an arbitrary filesystem path.

Add a minimal event list/detail, authenticated byte-range video playback, thumbnails, camera/source/recorded/discovered times, basic filters and pipeline health. Do not show an old snapshot without its capture time.

**Exit criteria:** duplicate/reordered pages, same-second clips, renamed cameras, token expiry, corrupt media, restart mid-download and missing disks behave deterministically. Unique source clips produce one logical event. AI being off does not prevent archiving. Imported fixture tests pass and actual-device gaps remain explicit.

## M3 · Ollama, structured observations and trustworthy summaries

**Objective:** local footage produces evidence-linked descriptions without cloud inference or invented certainty.

Discover the existing Ollama endpoint/version/models and enforce the local-only policy. Confirm actual vision support with synthetic images before private footage. Build model selection, resource status, a model test and optional download instructions. User approval is required for global Ollama changes or large downloads.

Implement bounded FFmpeg extraction, frame deduplication, chronology/frame hashes and visibility metadata. Send actual image inputs to native Ollama `/api/chat`, with `stream:false` and the supplied schema as `format`. No MP4 is posted to a fictional video API. Add timeout/cancellation, one inference at a time, fresh-event priority and bounded historical backlog.

Validate JSON and semantic evidence. Produce safe notification sentences from validated fields. Preserve raw model output only in private bounded diagnostic storage when explicitly enabled; normally store the validated observation and revision metadata. Add analysis retry/pause, failed/uncertain states and user corrections. No biometric identification, inferred intent or unchecked action execution.

**Exit criteria:** schema tests pass; IR colour and insufficient-motion evidence are suppressed by deterministic tests; invalid frame IDs fail; Ollama downtime leaves playable events; reanalysis does not create duplicate alerts. Benchmark selected model/preset on owner-approved labelled clips and document measured accuracy/latency rather than claiming a model is best.

## M4 · Complete daily-use interface and search

**Objective:** a polished, responsive product using real API state, not mock-only screens.

Implement the design specification: dashboard, camera detail, timeline, event detail, search, rules, activity inbox, storage and diagnostics. Finish mobile navigation, loading/empty/error/offline states, accessibility, keyboard operation, touch controls and system theme. Use original assets and explicitly licensed icons.

Add server pagination, filters, saved views, favourites, notes, local export, local deletion, snooze, read states and validated control/readback. Add grounded natural-language search through the provided filter schema; SQL is application-owned. Build deterministic daily counts plus an optional locally generated digest, with coverage gaps and links to underlying events. Ordinary search must work without Ollama.

**Exit criteria:** a camera rename or reconnect does not break history; filters and detail links survive reload; keyboard/screen-reader basics and mobile viewports pass; all capability-disabled actions explain why; successful commands are confirmed by upstream readback. Test disarm only with explicit owner authorization, never as part of unattended acceptance.

## M5 · Notification rules and real phone delivery

**Objective:** a usable rule engine and at least one genuinely tested background delivery path.

Implement the notification-rule contract, entity-scoped matching, unknown policy, cooldowns, app-only snooze, quiet hours/timezones, idempotent outbox, expiry, provider retries and delivery history. Basic generic event alerts can operate without AI; descriptive alerts wait only to a configured deadline. Historical backfill does not flood the phone.

Build an in-app inbox first. Add Web Push as an explicit optional transport with service worker, VAPID configuration, encrypted subscriptions, secure origin checks and browser permission flow. Clearly disclose that standard Web Push uses browser-vendor push services; local analysis does not imply local-only delivery. Optional self-hosted ntfy for Android is a separate provider, not an excuse to call an open-tab toast background push.

Explain and test private-server reachability separately from notification delivery. A phone can receive push yet fail to open a private clip while away from home. No automatic router forwarding, public tunnel, firewall exposure or certificate installation.

**Exit criteria:** rule tests cover uncertainty and daylight/IR behaviour; duplicate jobs do not send duplicate logical alerts; real chosen phone receives a notification with app closed/screen locked on the approved network path. Test Wi-Fi and cellular separately when relevant. Record device/OS/browser/provider and observed delay; do not fabricate delivery guarantees.

## M6 · Reliability, retention, backup and release handoff

**Objective:** a maintainable personal-use release with honest limitations.

Implement owner-approved retention settings, favourite protection, free-space reserve, offline disk handling, local-only deletion defaults, consistent backups, tested restore, schema migration tests and safe uninstall documentation. Keep credentials/OS vault data out of ordinary portable backups. A restore must not replay old notifications or silently inherit somebody else's sessions.

Add redacted support exports, dependency/licence review, restore/runbook documentation and optional user-approved startup. Test crashes, GPU contention, expired auth, rate limits, sleep/resume, network loss, missing volumes and storage pressure. Provide separate liveness/readiness and last-success metrics.

Complete `BUILD_STATUS.md`, the actual hardware validation report, model evaluation results, phone report and a known-limitations document. Run the audit prompt. A soak test should use the configured respectful polling, not artificial API load.

**Exit criteria:** reproducible build/test commands; no secret in repository or public logs; passing critical automated tests; backup/restore evidence; actual compatibility/delivery checks either pass or are prominently limited. The release label must match evidence: imported-clip demo, hardware-verified core, or experimental live build.

## M7 · Experimental true live view and additional device controls

Only after M0–M6 are usable, inspect the pinned library's actual streaming support. Implement a server-side bounded session with capability negotiation, short user-triggered duration, disconnect cleanup, no permanent camera wakefulness and clear battery warning. Establish codec/browser compatibility without redistributing unreviewed encoders.

Prove that frames are arriving from a current live session. A preview, stalled frame or replay is never labelled LIVE. Show connection state, media age and failure reason. Test concurrent requests, expired sessions, account changes and shutdown cleanup. Additional controls and listen-in audio require per-model tests. Two-way talk, doorbell calling and continuous NVR capture remain unsupported until independently proven.

**Exit criteria:** measured real-camera stream startup/playback/reconnect/cleanup, reviewed licences, no false-live status. Otherwise leave the feature disabled with a useful explanation. The core release does not depend on it.

## Handoff format after every session

State the completed milestone/tasks, exact commands run, actual test results, changed files, unresolved external gates and next executable task. Include no credentials, signed clip URLs or private screenshots. Never replace the status report with “everything should work.”
