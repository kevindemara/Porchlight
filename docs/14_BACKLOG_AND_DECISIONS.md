# 14 · Decisions, task dependencies and future scope

## Settled architectural decisions

| Decision | Chosen approach | Reason / consequence |
|---|---|---|
| Product form | Independent Windows-hosted responsive app; Android-first delivery test target | One coherent UI and existing local hardware; phone OS is confirmed in setup |
| Camera connection | blinkpy behind a replaceable adapter | Centralizes a fragile unofficial dependency and permits fixtures/version upgrades |
| Recording source | Separate cloud, Sync Module local-storage and import providers | A cloud history helper is not assumed to download all local storage |
| Processing | Download real clips, then analyse sampled frames | Avoids replayed-RTSP/frozen-frame complexity for a motion-clip camera |
| AI | Existing native Ollama; local vision models only | No paid inference dependency; GPU contention and unknown capabilities are visible |
| Data | SQLite plus ordinary local media files | Simple single-PC deployment; disciplined writer/backup design required |
| Frontend | React/TypeScript, Vite build served by FastAPI | Same-origin auth/media; no Node production server required |
| Queue | Durable DB jobs, leases and outbox | Restart safety without Redis; one application worker process initially |
| Alerts | In-app inbox plus explicit Web Push / optional self-hosted ntfy | Delivery and remote access are distinct; no open-tab-only pretence |
| Live view | Experimental after core proof | Prevents unreliable live support from blocking useful local clip AI |
| Upstream code | Licensed dependency reuse and independent implementations | No indiscriminate merger of incompatible or missing licences |
| Safety | Evidence-linked descriptions, no autonomous physical/security actions | Model output cannot disarm cameras, call authorities or make identity decisions |

## Resolve in setup, not by guessing

### Owner's next priorities · 2026-10-08

After the current navigation/Activity description refinements, work through these in order. Automated code tests do not complete the owner/hardware acceptance items.

Next-step review, 2026-10-08: the owner wants to test on Android before building a Cloudflare tunnel. A short USB/ADB loopback test is the simplest first candidate; LAN-only HTTPS is the untethered alternative. See [phone testing routes](REMOTE_AND_PHONE.md#first-android-test-without-a-tunnel). Prepare a fresh local backup before access changes, test sign-in/media/live audio and capture/reconnect on the actual phone, and fix issues found before adding internet access. These are proposals only; no ADB/proxy package, certificate, firewall rule or tunnel has been configured. Push remains a later exact-HTTPS-origin/optional-dependency/device-delivery gate.

1. Configure owner-approved authenticated HTTPS phone access and optional push packages, then test Android home-screen use, locked-screen alerts, Wi-Fi/cellular and tap-to-play.
2. When the new cameras arrive, validate storage/module compatibility and genuinely new no-plan retrieval, including post-restart recording, plus live/Record/Snapshot/reconnect.
3. Complete a 24–48-hour soak, sleep/resume and network-loss checks, and a fresh backup/restore.
4. Verify clean-clone installation, add automated repository checks, resolve remaining licence/notice gaps and refresh superseded documentation.
5. Later, experiment with two-way talk: first prove a short owner-triggered microphone transmission can reach the Blink doorbell; proceed to the full interface only after that feasibility gate passes.

Completed by owner confirmation, 2026-10-08 (removed from the remaining list):

- Fresh Blink clips automatically import and analyze across a restart.
- Representative daytime/nighttime Qwen descriptions and face-match accuracy reviewed locally.

These are owner-reported acceptance results, not new agent-run measurements. No latency, accuracy score or new-camera/no-plan result is inferred. The owner requested another one-time reminder in one hour; the existing `porchlight-next-steps-reminder` heartbeat was updated to cover only the four remaining tasks and pause after delivery.

Implementation decisions, 2026-10-06: build/test locally on Windows and push only after completion/testing to a private repository. Use the existing native Ollama and Qwen vision alias initially, without global reconfiguration. Configure a private app-local FFmpeg installation under LOCALAPPDATA; no system PATH edit or bundled binary. Preserve imported recordings independently of model readiness. Keep private-media inference disabled until the local-only policy and grounded analysis gates pass.

Owner update, 2026-10-08: commit the current development work and create the private `kevindemara/Porchlight` repository for the first source push. This supersedes the earlier requirement to wait for release completion before a private source snapshot. Development remains local; hardware, phone and release acceptance are still separate gates, and repository visibility remains private.

Owner bootstrap uses a short-lived, single-use token obtained by the same-origin local setup page through a custom-header request rather than a printed console token. This makes first setup usable from the built interface while retaining strict Host/Origin/fetch-site checks, a loopback binding, token expiry and single-owner database uniqueness. The token is held only in page memory; it is not logged or stored in the browser. Tests exercise replay, expiry and competing claims.

Exact camera/module types; storage status; active subscription/trial/legacy entitlement; actual retrieval path; phone OS/browser; available Python/Node/FFmpeg; installed Ollama vision models and local-only configuration; selected archive disk; storage budget; acceptable alert delay; and whether phone access is needed away from home.

Unknowns should produce a visible capability or setup state. They are not an excuse to stop building independent functionality, and not permission to invent positive test results. Hardware/OS-bound credentials and device changes need owner participation, not secret requests in a coding chat.

## Dependency task map

| ID | Task | Depends on |
|---|---|---|
| CORE-01 | Authenticated shell, config, migrations, same-origin UI | None |
| BLINK-01 | Pinned adapter API map and fixtures | CORE-01 |
| BLINK-02 | Local login/vault and inventory | BLINK-01 |
| BLINK-03 | Separate cloud/local clip retrieval and capability report | BLINK-02 |
| STORE-01 | Atomic files, stable events, leased jobs/outbox | CORE-01, BLINK-01 |
| STORE-02 | Playback, overlap discovery, recovery, source tombstones | STORE-01, BLINK-03 |
| AI-01 | Local-only Ollama/vision discovery | CORE-01 |
| AI-02 | Frames, structured observations, semantic validation | STORE-01, AI-01 |
| UI-01 | Camera dashboard/timeline/detail | STORE-02 |
| UI-02 | Search/favourites/notes/digests | UI-01, AI-02 |
| ALERT-01 | Rule engine, inbox, idempotent dispatch | AI-02, STORE-01 |
| ALERT-02 | Secure phone delivery and private access testing | ALERT-01, CORE-01 |
| OPS-01 | Retention, backups/restore, redacted diagnostics | STORE-02 |
| RELEASE-01 | Acceptance report, real-device gates, licence audit | UI-02, ALERT-02, OPS-01 |
| LIVE-01 | Actual-stream experiment and capability validation | RELEASE-01 |
| LIVE-02 | Optional two-way-talk feasibility experiment, then microphone controls if proven | LIVE-01; ALERT-02 for HTTPS phone use |

A developer may implement mock-independent tasks concurrently, but must avoid concurrent Blink account login/poll actors and conflicting database migrations.

## Later enhancements, not first-release requirements

**Two-way talk — owner-requested, deferred 2026-10-08:** investigate the legitimate authenticated Blink relay's outgoing audio format and speaker activation. Incoming AAC support does not establish outgoing audio support; the installed Blink adapter has no microphone-transmission implementation. First verify a short, explicitly triggered local transmission on the owner's doorbell. If successful, add permission-based microphone capture and a Hold to talk control that stops on release, disconnect, navigation or session expiry; test latency, feedback, cleanup and authenticated HTTPS phone use. Keep it capability-gated and optional, preserve video/listening when unsupported, and retain private audio locally except for the intended Blink relay transmission. No implementation or hardware transmission test is authorized by this backlog-only request; the owner wants to experiment later.

**Zones and line crossing:** add only after establishing trustworthy object geometry/tracking. A vision-language model's prose or guessed boxes is not an accurate detector. Review detector code AND model-weight licences, establish a ground-truth dataset, and measure short-clip/occlusion limitations. Keep activity/privacy zones distinct from camera settings.

**Semantic embeddings:** optional local retrieval after typed/full-text search works. Preserve evidence links and explain recall limits. No vector database service is required for the initial build.

**Cross-camera grouping:** possible event clustering, not person identity recognition. Avoid double-counting in digests and never assert a person/car is the same based solely on similar appearance.

**Native desktop/mobile wrapper:** optional later Tauri or Android shell after the web/API workflows and delivery constraints are proven. No promise that a wrapper bypasses mobile OS background restrictions.

**Additional camera providers:** adapter architecture can later support legitimate continuous streams from compatible non-Blink devices. This does not create a native RTSP feed on existing Blink hardware. Do not require replacement hardware for the first prototype.

**Home Assistant/MQTT interoperability:** optional authenticated outbound events using minimal metadata. Never an insecure arbitrary webhook forwarder. Core installation remains standalone.

**Multiple households/users:** defer until access-control boundaries, isolation, audit and operational responsibilities are designed. The first release is a private single-owner installation, not a hosted multi-tenant surveillance service.

## Explicit non-goals

Owner-approved extensions, 2026-10-07–08: optional YuNet face detection and opt-in local SFace recognition for named owner-enrolled/reviewed profiles supersede the original exclusion of all identity recognition. Automatic detection starts off and is independent of Qwen. Uncertain faces remain unnamed, and results never trigger security/physical actions. See [FACE_DETECTION.md](FACE_DETECTION.md) and AGENTS.md for intake, privacy and owner accuracy gates.

No official Blink paywall bypass, credential interception, stealth account use, identification outside the opt-in named-profile scope, demographic inference, emotion/criminal-intent scoring, continuous battery-camera streaming, emergency-response guarantee, automatic police notification, or unrestricted AI actions. No commercial-brand claim for the working title. No bundled upstream source assets, model weights or encoders without their licence/distribution review.
