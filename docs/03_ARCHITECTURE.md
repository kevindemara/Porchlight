# 03 · Architecture

## Chosen design

Build a **single-host, modular application**, not a collection of entire third-party camera platforms. The first supported environment is Windows with native Ollama already running. Docker/WSL is not required for the core.

| Layer | Chosen direction |
|---|---|
| Frontend | React + TypeScript + Vite, router, query cache, accessible component primitives |
| Backend | Python + FastAPI + Pydantic; one production application process |
| Blink integration | `blinkpy` behind a replaceable provider interface |
| Persistence | SQLite on a local disk, SQLAlchemy/Alembic migrations, WAL, busy timeout |
| Background work | SQLite-backed jobs with leases, retries, reconciliation; no Redis required |
| Media | Local files, UUID paths, atomic writes, SHA-256, FFmpeg/ffprobe |
| AI | HTTP client to local Ollama; validated JSON observations |
| UI updates | Authenticated server-sent events (SSE) plus ordinary API queries |
| Phone notifications | Optional Web Push/VAPID; self-hosted ntfy alternative |
| Secrets | OS-backed vault; Windows DPAPI-protected secret envelope |
| Deployment | Vite static build served by FastAPI, optional trusted HTTPS reverse proxy |

These are project decisions, not claims that this is the only valid stack. Resolve current stable versions and runtime compatibility during M0. SQLite WAL requires same-machine coordination; do not place its live database on a network filesystem. [T3](15_SOURCES_AND_VERSIONING.md#t3)

## Data flow

```text
Blink cloud / Sync Module cloud-mediated clip access
  -> account-scoped adapter + request scheduler
  -> source inventory and durable discovered-clip records
  -> download jobs -> validated local media -> timeline immediately
  -> frame-extraction jobs -> bounded local Ollama analysis
  -> schema + evidence checks -> saved observation revision
  -> deterministic rule engine -> durable notification outbox
  -> in-app SSE / optional Web Push / optional self-hosted ntfy

React UI -> authenticated same-origin API -> stored data and queued commands
Ollama is called only by the backend, never directly by the browser.
```

A new clip appears in the timeline before analysis completes. AI and notification availability must never be prerequisites for preserving the recording.

## Process and concurrency model

Run one production Uvicorn worker with a FastAPI lifespan supervisor. The supervisor owns the durable job runner and a single account actor. Do not use development auto-reload or multi-worker mode in production; they can duplicate polling and jobs. Enforce a process lock at startup.

Blink operations are serialized through the account actor; local-storage workflows may also require a module lock. Download media sequentially by default. One Ollama inference at a time. FFmpeg work runs as bounded subprocesses with timeouts; never block the HTTP event loop. Database transactions are short and never held open during network/model work.

Claim jobs atomically, commit a lease, execute outside the transaction, then commit results. Extend leases for long work and reclaim expired leases on startup. Use idempotent result keys and an outbox transaction, because a lease alone does not prevent duplicates after a crash.

Expose separate health for API liveness, DB writeability, worker heartbeat, Blink auth/sync, media space, and Ollama readiness. A process can be alive while the recording source is unavailable.

## Repository layout to implement

```text
AGENTS.md / README.md / BUILD_STATUS.md / docs/ / prompts/
apps/web/
  src/{app,routes,components,features,lib,styles}/
  public/                         # own icons only; no private media
services/porchlight/
  api/                            # auth, settings, media, events, controls
  domain/                         # typed entities, services, capabilities
  providers/{base.py,blink/,imports/,demo/}
  ingestion/                      # discovery, dedup, durable media transfer
  ai/                             # Ollama client, frames, validators, summaries
  jobs/                           # durable queue, leases, retries
  notifications/                  # rules, outbox, delivery adapters
  storage/                        # repositories, migrations, retention, backups
  security/                       # vault, sessions, CSRF, URL validation
  observability/                  # redaction, metrics, diagnostic export
  __main__.py                     # one application entrypoint
schemas/                          # versioned exchange contracts
examples/                         # synthetic fixtures only
scripts/                          # PowerShell tooling
tests/                            # unit, integration, e2e, contracts, fixtures
```

Suggested test folders: `tests/unit`, `tests/integration`, `tests/e2e`, `tests/contracts`, `tests/fixtures`. Generate frontend API types from the actual OpenAPI contract, not hand-copied interfaces.

## Provider boundary

Our interfaces describe our own contract; they are **not asserted blinkpy method names**:

`begin_auth`, `complete_auth`, `restore_session`, `discover_inventory`, `probe_capabilities`, `list_clip_page`, `prepare_clip_download`, `download_clip`, `request_snapshot`, `set_network_armed`, `set_camera_motion`, `open_live_session`, `close_live_session`.

Use typed results/errors and an explicit auth-challenge DTO. The Blink implementation translates to the exact installed library. App imports and tests must not rely on its private dictionaries. Where a private bridge is unavoidable for missing upstream coverage, isolate/version-test it inside the adapter and document it as brittle.

## Runtime paths

Suggested default data root: `%LOCALAPPDATA%\Porchlight`. Use a configurable local media directory separate from source, for example `D:\PorchlightMedia` only after the user selects an existing suitable disk. Do not assume drive letters exist.

Store the DB, secrets envelope, temporary files, media, thumbnails, logs, and backups in clearly separated subdirectories. Keep runtime files out of Git. AI frames are derived personal data and must obey retention/deletion rules.

## Failure isolation

Blink outage: preserve local playback/search, mark sync stale, retry conservatively. Ollama outage: retain clips, queue bounded analysis, deliver a generic event alert when enabled. Disk full: pause downloads safely and alert; no deletion of favourites to conceal the problem. Notification outage: show durable failures and keep original events. Backend offline: service-worker shell can show “server unavailable” but must not suggest monitoring continues.

The optional future live bridge and notification sidecars have narrow local interfaces. Do not embed them into the core before there is a proven need.
