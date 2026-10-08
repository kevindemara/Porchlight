# 15 · Primary sources and version-verification ledger

Research date: **October 6, 2026**. The references below informed the design; they are not proof that an installed library, camera, model or phone has been tested. This package contains independently written specifications, not copies of upstream applications. Recheck relevant primary sources before implementation and upgrades. Repository default branches are mutable.

## Blink

<a id="b1"></a>
### B1 · Official local storage and backup

[Blink: Local Storage with Sync Module](https://support.blinkforhome.com/en_US/using-your-sync-module/sync-module-2-local-storage-operation).

Supports the hardware/storage boundary, the distinction between local recording and daily subscription clip backup, legacy-device differences and Core's lack of local storage. Does not establish third-party API compatibility for the owner's system.

<a id="b2"></a>
### B2 · Official subscription features

[Blink: Subscription Plan Features](https://support.blinkforhome.com/en_US/subscription-features/subscription-plan-features).

Used to distinguish legitimate free official capabilities from paid cloud/AI entitlements. Porchlight performs its own analysis only on recordings it can legitimately obtain; it does not unlock official paid features. Feature eligibility can vary by device/account/region.

## Existing projects and their code

<a id="r1"></a>
### R1 · blinkpy README, examples and licence

[fronzbot/blinkpy](https://github.com/fronzbot/blinkpy).

MIT-licensed primary adapter candidate. Reviewed auth, camera controls, download and tentative local-storage protocol notes. The README discourages API calls faster than 60 seconds. Its own library refresh default is not the application's selected background schedule. Cloud-mediated local retrieval is not a fully offline camera connection.

<a id="r2"></a>
### R2 · blinkpy releases

[blinkpy releases](https://github.com/fronzbot/blinkpy/releases).

The reviewed release page included v0.25.9, with earlier authentication and live-view endpoint fixes. This is an observed candidate, **not a version tested by this package**. Verify the actual release available during implementation, inspect changes and lock a tested version/commit; do not track an unpinned branch in production.

<a id="r3"></a>
### R3 · blinkpy recording implementation

[blinkpy.py on the reviewed dev branch](https://raw.githubusercontent.com/fronzbot/blinkpy/dev/blinkpy/blinkpy.py).

Used to inspect the cloud metadata/download path and why the latest cached video/bulk-helper defaults are not a complete ingestion design. All source mapping must be redone against the pinned package.

<a id="r4"></a>
### R4 · Sync Module implementation

[sync_module.py on the reviewed dev branch](https://raw.githubusercontent.com/fronzbot/blinkpy/dev/blinkpy/sync_module.py).

Used to inspect separate local manifest/prepared-download behaviour. This is a code path to evaluate, not proof that every XR/2/firmware combination works. Private interfaces require an isolated compatibility bridge and regression tests.

<a id="r5"></a>
### R5 · Homebridge Blink integration

[BitWise-0x/homebridge-blink-security](https://github.com/BitWise-0x/homebridge-blink-security) · [reviewed licence file](https://raw.githubusercontent.com/BitWise-0x/homebridge-blink-security/main/LICENSE).

Reference for capabilities, authentication/streaming challenges and motion delivery delays. The reviewed licence contains GPLv3 text. No source transplant is authorized by this package; do not assume a separate process automatically resolves every distribution/licence concern. Independently implement UI/workflows or obtain an appropriate review before reuse.

<a id="r6"></a>
### R6 · Recorded-clip RTSP bridge

[roger-/blinkbridge](https://github.com/roger-/blinkbridge).

README describes replaying downloaded recordings and freezing the last frame, not continuous real-time Blink video. It flags local-storage issues. No clear licence was identified in the reviewed root listing; verify before any source reuse. Publicly visible code is not automatically permissively licensed.

<a id="r7"></a>
### R7 · LLM Vision

[valentinfrlch/ha-llmvision](https://github.com/valentinfrlch/ha-llmvision) · [licence](https://raw.githubusercontent.com/valentinfrlch/ha-llmvision/main/LICENSE).

Reference for image/video event descriptions and timeline/notification concepts. Reviewed Apache-2.0 licence. Porchlight does not require Home Assistant or copy this application's implementation by default.

<a id="r8"></a>
### R8 · Home Assistant Blink documentation

[Home Assistant Blink integration](https://www.home-assistant.io/integrations/blink/).

Documents controls/recording actions, update caveats and no standard integration live view. Used as integration context rather than a Porchlight runtime dependency.

<a id="r9"></a>
### R9 · Frigate generative summaries

[Frigate generative review summaries](https://docs.frigate.video/configuration/genai/genai_review/) · [core licence](https://raw.githubusercontent.com/blakeblackshear/frigate/dev/LICENSE).

Reference for grounded event-review summaries. Core source licence reviewed as MIT; external models/services/assets may have different terms. No Frigate server, Frigate+ service or Frigate model is required by this design.

<a id="r10"></a>
### R10 · Licence review scope

The per-project licence links above, plus [blinkpy licence](https://github.com/fronzbot/blinkpy/blob/dev/LICENSE.md), are the review entry points. Record actual version/commit, SPDX identifier, attribution/NOTICE obligations, copied files and third-party model/asset terms in the implemented app. A licence observation is not a comprehensive distribution review or legal opinion. The historical [BlinkMonitorProtocol repository](https://github.com/MattTW/BlinkMonitorProtocol) is optional background only; this package does not rely on unverified historical endpoints.

## Ollama and model candidates

<a id="a1"></a>
### A1 · Vision inputs

[Ollama vision documentation](https://docs.ollama.com/capabilities/vision). Image inputs are used with chat; frame extraction is an application step.

<a id="a2"></a>
### A2 · Structured outputs

[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs). JSON Schema constrains shape; application validation still checks structure and semantic evidence.

<a id="a3"></a>
### A3 · Native API and discovery

[Chat endpoint](https://docs.ollama.com/api/chat) · [list installed models](https://docs.ollama.com/api/tags) · [running models](https://docs.ollama.com/api/ps).

Verify supported fields and runtime/model behaviour. Inspect `/api/show` capabilities where supported; use an explicit synthetic vision test if metadata is insufficient. No guarantee that every listed optional parameter works on every model/runtime.

<a id="a4"></a>
### A4 · Qwen vision candidate

[Ollama qwen3-vl:8b](https://ollama.com/library/qwen3-vl:8b).

The reviewed tag advertises vision and lists an approximately 6.1 GB Q4_K_M artifact; the family includes 4B and 8B variants. Disk artifact size is not total GPU memory consumption. Record exact digest/licence and evaluate against owner footage. This is a baseline candidate, not a newest/best model claim.

<a id="a5"></a>
### A5 · Optional comparison candidate

[Ollama gemma4:12b](https://ollama.com/library/gemma4:12b).

The reviewed tag provides an additional local vision candidate. It is not installed, benchmarked or bundled by this package. Inspect the current weight licence and runtime support before use or redistribution.

<a id="a6"></a>
### A6 · Local service, cloud controls and resource behaviour

[Ollama FAQ](https://docs.ollama.com/faq).

Documents local serving and cloud-disable configuration. Existing global settings belong to the owner: do not silently change/restart their Ollama installation. An endpoint on loopback alone is not proof a selected model is locally executing.

## Notifications and operations

<a id="n1"></a>
### N1 · Web Push

[MDN Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API). Reference for service-worker/background delivery, subscriptions and security considerations. Verify chosen browser/device behaviour in the real phone test.

<a id="n2"></a>
### N2 · Secure-context requirement

[MDN Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API). HTTPS/secure-context deployment matters; the localhost exception is not a blanket exception for plain LAN-IP URLs.

<a id="n3"></a>
### N3 · ntfy on phones

[ntfy phone subscriptions](https://docs.ntfy.sh/subscribe/phone/). Reference for Android self-hosted delivery choices and foreground/battery tradeoffs. No universal background-delivery claim is inferred from provider acceptance.

<a id="n4"></a>
### N4 · ntfy server configuration

[ntfy configuration](https://docs.ntfy.sh/config/). Optional self-hosted deployment must explicitly review authentication, anonymous access, topics, TLS and platform relay settings; not a mandatory core service.

<a id="t3"></a>
### T3 · SQLite WAL

[SQLite write-ahead logging](https://www.sqlite.org/wal.html). Informs local-filesystem/concurrency/backup constraints. Use consistent backup mechanisms, not an unsafe copy of an active database alone.

<a id="t4"></a>
### T4 · FFmpeg redistribution

[FFmpeg legal considerations](https://ffmpeg.org/legal.html). Build configuration affects obligations; using an installed binary avoids pretending this documentation grants redistribution rights.

<a id="o1"></a>
### O1 · Codex project instructions

[Official Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md/).

Reference for project-level instruction discovery. Keep root instructions concise and load detailed docs as needed. No bypass of Codex's approval/sandbox controls is required. Building the app with Codex is distinct from adding any cloud AI dependency to the app.

## Implementation version ledger — not yet completed

| Component | Research observation / design choice | Installed/tested version |
|---|---|---|
| blinkpy | v0.25.9 observed; verify current stable/API mapping | NOT TESTED |
| Python / FastAPI / Pydantic / SQLAlchemy / Alembic | Proposed backend; choose compatible supported releases | NOT SELECTED |
| Node / React / TypeScript / Vite | Proposed UI/build stack; inspect existing tools | NOT SELECTED |
| Ollama | Existing user installation must be inspected | UNKNOWN |
| Vision model | Local candidates above; owner-approved evaluation | UNKNOWN |
| FFmpeg / ffprobe | Local installed binary, licence verified | UNKNOWN |
| Notification libraries/provider | Optional transport chosen during setup | NOT SELECTED |

For every upgrade: read relevant changes; lock exact versions; run adapter/auth/download, schema/semantic, migration, media and notification tests; keep rollback backups; update the ledger. Record observations, not guessed guarantees.
