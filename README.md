# Porchlight — local AI for your Blink cameras
## Windows development build · independent Blink companion

**The local development build is runnable.** It includes Blink sign-in/inventory, durable cloud archiving and resumable historical retrieval, MP4/JPEG imports, protected playback, local AI descriptions with workload presets and verified sampled-image review, filters/search/digests, saved views, notification rules/inbox, previewed retention, verified backup/restore and independent worker diagnostics. Guided setup, camera network/local grouping, date-grouped Activity and authenticated live state updates are implemented. Navigation is Live View, Activity, Faces and Settings. Activity brings archived clips, live recordings and snapshots together with All / Recordings / Snapshots and clear source labels; Live View includes Manage cameras, explicit Record/Snapshot controls and optional camera audio with mute/volume controls. Saved live recordings preserve supplied audio even while listening is muted. Settings has six sections, while the notification bell opens the inbox. Manual camera controls use observed read-back; Sync Module local retrieval is a capability-gated candidate awaiting new hardware. Optional browser push and home-screen installation controls are implemented; approved pinned encryption dependencies passed a native synthetic round trip. The owner confirmed Android home-screen installation, reopening and a successful phone notification test. Descriptive alerts and tap-to-recording have synthetic regression coverage; real new-clip lock-screen display and authenticated tap-to-play remain owner-assisted acceptance checks. See [current evidence](BUILD_STATUS.md), [known limitations](docs/KNOWN_LIMITATIONS.md), [release checks](docs/RELEASE_CHECKLIST.md) and [requirement audit](docs/IMPLEMENTATION_AUDIT.md).

For installation, follow the [beginner quick start](docs/QUICK_START.md). Run `./setup.ps1 -Check`, then `./setup.ps1` to review and approve dependency installation. On a prepared checkout run `./start.ps1`, then open <http://127.0.0.1:8765>. New owners enter the setup wizard; **AI is optional**, with a read-only machine check, local installation instructions, synthetic image test and explicit skip path. See [optional AI](docs/LOCAL_AI_SETUP.md) and [phone connection options](docs/PHONE_SETUP.md), including [direct home HTTPS](docs/DIRECT_HTTPS.md) without a phone VPN and an optional [private Cloudflare backup](docs/CLOUDFLARE_BACKUP.md). These need explicit network setup; clean-machine/cellular acceptance remains pending. Developer commands are in [local development](docs/LOCAL_DEVELOPMENT.md). The documents below preserve the full target specification.

Porchlight is a working title for an independent, personal-use camera companion. The goal is a polished Blink-like everyday experience with locally stored recordings and Ollama-generated descriptions, without requiring a paid Blink plan or paid AI API **where the user's actual hardware/account provides a working subscription-free recording source**. It must not impersonate Blink, copy its branding, or claim official affiliation.

## Start here

1. Extract this folder to `C:\Projects\Porchlight` (or another local development directory outside OneDrive).
2. Follow the [quick start](docs/QUICK_START.md) to check prerequisites and run the optional interactive installer. Codex is not needed to run the app.
3. Start Porchlight, create your local owner and follow the setup wizard. [START_HERE_CODEX.md](START_HERE_CODEX.md) preserves the original developer brief.
4. Enter Blink credentials and verification codes only into the local setup screen. Do not paste them into a conversation, a source file, or this package.
5. Keep the official Blink app and existing recording setup until the hardware validation gate passes. No part of this project should cancel, purchase, or modify a subscription automatically.

The project-level [AGENTS.md](AGENTS.md) supplies persistent engineering instructions. Codex's documented instruction discovery supports this file; the detailed specifications remain separate so they can be read milestone by milestone. [O1 in Sources](docs/15_SOURCES_AND_VERSIONING.md#o1)

## The application we are building

A responsive camera dashboard; event timeline; clip playback and export; favourites and notes; network arm/disarm and supported camera controls; local AI descriptions such as a vehicle passing; filters and grounded natural-language event search; notification rules, snooze and quiet hours; daily summaries; storage retention; and clear health diagnostics. Experimental live view and additional device controls are capability-gated, not presumed to work.

The implemented runtime is a Windows-native Python/FastAPI service, a React/TypeScript interface built with Vite, a local SQLite database, a local media directory, and the user's existing native Ollama installation. The normal installation does **not** require Home Assistant, Frigate, Homebridge, Supabase, Vercel, Docker, a cloud database, or an AI API key. Optional notification/remote-access enhancements are isolated from the core.

Optional [local face detection and recognition](docs/FACE_DETECTION.md) reports sampled face counts, timestamps and size/sharpness flags. The **Faces** page shows reviewable groups, lets the owner select up to 12 images across cards for one name, suggests possible existing names and can rescan the latest 20 videos. Verified local SFace then suggests matches in later clips; an optional strict switch can add one clear sample from a future recording to a well-seeded profile. Templates are encrypted for the Windows user, uncertain matches stay unnamed, and automatic detection defaults off. Both models require explicit local installation.

## The subscription-free boundary

Blink documents local recording through Sync Module 2 with USB storage and Sync Module XR with microSD, for compatible cameras. Core has no local-storage support; older camera/account configurations can have different storage entitlements. [B1](docs/15_SOURCES_AND_VERSIONING.md#b1)

**Support in Blink's official app does not prove support through an unofficial library.** M1 must verify that Porchlight can actually list and retrieve newly created clips without an active paid/trial recording entitlement. When that cannot be verified, show `unverified` or `blocked`, not “subscription-free ready.”

“Local AI” does not mean Blink becomes an offline/LAN-only camera. The selected adapter still depends on Blink's services, and local-storage retrieval can involve a cloud-mediated transfer. [R1](docs/15_SOURCES_AND_VERSIONING.md#r1) It is not a bypass of paid entitlements.

## Known user environment and unresolved facts

The current PC has a verified RTX 5070 Ti (16,303 MiB), 31.6 GiB RAM and Ryzen 9 7950X3D. Native Ollama is already installed; the existing local vision model has passed native tests. The current doorbell uses Sync Module Core and an owner-confirmed paid plan. Core provides no removable recording storage. Other PCs and hardware require their own checks; no model is bundled.

Start by evaluating a locally installed vision-capable model. `qwen3-vl:8b` is a documented baseline candidate, with `qwen3-vl:4b` as a lighter candidate and `gemma4:12b` as an optional comparison. These are candidates, not a claim that any one is universally best. No model is bundled. [A4–A5](docs/15_SOURCES_AND_VERSIONING.md#a4)

## Read the documents in this order

| File | Purpose |
|---|---|
| [00 · Product requirements](docs/00_PRODUCT_REQUIREMENTS.md) | Outcomes, user stories, non-goals |
| [01 · Feature matrix](docs/01_FEATURE_MATRIX_AND_SCOPE.md) | What is core, conditional, experimental, or deferred |
| [02 · Blink compatibility](docs/02_BLINK_COMPATIBILITY_AND_NO_SUBSCRIPTION.md) | The no-subscription decision tree and hardware gate |
| [03 · Architecture](docs/03_ARCHITECTURE.md) | Services, data flow, repository layout |
| [04 · Repo research and licences](docs/04_REPOSITORY_RESEARCH_AND_LICENSES.md) | What to reuse versus independently implement |
| [05 · Blink adapter](docs/05_BLINK_ADAPTER_AND_INGESTION.md) | Auth, polling, clip retrieval, compatibility boundaries |
| [06 · Ollama pipeline](docs/06_OLLAMA_AND_AI_PIPELINE.md) | Model discovery, frame selection, truthful descriptions |
| [07 · Data and API](docs/07_DATA_MODEL_AND_API.md) | Database, jobs, HTTP API, errors |
| [08 · UI/UX](docs/08_UI_UX_SPECIFICATION.md) | Screens, interaction details, accessibility |
| [09 · Notifications](docs/09_NOTIFICATIONS_AND_REMOTE_ACCESS.md) | Phone alerts, secure contexts, remote access |
| [10 · Security and reliability](docs/10_SECURITY_PRIVACY_AND_RELIABILITY.md) | Credentials, footage, recovery, abuse prevention |
| [11 · Windows operations](docs/11_WINDOWS_SETUP_AND_OPERATIONS.md) | Setup, startup, storage, backups, troubleshooting |
| [12 · Implementation plan](docs/12_IMPLEMENTATION_PLAN.md) | Dependency-ordered milestones and exit criteria |
| [13 · Tests](docs/13_TESTS_AND_ACCEPTANCE.md) | Automated and real-device acceptance tests |
| [14 · Decisions and backlog](docs/14_BACKLOG_AND_DECISIONS.md) | Settled choices, remaining decisions, later features |
| [15 · Sources](docs/15_SOURCES_AND_VERSIONING.md) | Primary references and version verification |
| [16 · Hardware report](docs/16_HARDWARE_VALIDATION_REPORT_TEMPLATE.md) | A blank evidence template, not a passing report |

`prompts/` contains the AI instructions and follow-on Codex prompts. `schemas/` contains JSON contracts. `examples/` contains synthetic, non-evidentiary examples. `scripts/preflight.ps1` only inspects local prerequisites and Ollama metadata; it does not connect to Blink or install anything.

## Completion standard

A nice-looking demo is not completion. A working imported-clip analyzer is not proof of Blink compatibility. A recording made during a free trial is not proof of no-subscription recording. A successful push-provider response is not proof a phone displayed the alert. Each must be measured separately and documented in [BUILD_STATUS.md](BUILD_STATUS.md).
