# 07 · Data model and HTTP API

## Persistence rules

SQLite lives on a local filesystem. Enable foreign keys, WAL and a busy timeout, and use versioned migrations. Keep transactions short; never hold a write transaction during Blink, FFmpeg or Ollama work. Use a consistent backup API or stop/checkpoint safely rather than copying only a busy WAL database file. [T3](15_SOURCES_AND_VERSIONING.md#t3)

UUIDs identify application records. Store UTC instants with explicit offsets and the source's raw timestamp/provenance. A timestamp that could not be normalized remains visibly uncertain. Store filesystem paths as app-owned relative paths, never user-provided arbitrary paths.

## Tables and relationships

| Table | Essential fields/constraints |
|---|---|
| `users` | id, login_name, password_hash, created_at; single owner initially |
| `sessions` | id_hash, user_id, csrf_secret_hash/reference, created/expiry/revoked; no raw session token |
| `settings` | versioned nonsecret settings; timezone, retention and feature flags |
| `blink_accounts` | local id, upstream id protected from client exposure, auth_state, vault_ref, last_sync |
| `networks` | account_id, upstream network id, local name, observed_armed, observed_at |
| `sync_modules` | network_id, upstream id, family, firmware, storage_state, capability_json |
| `cameras` | account/network/module refs, upstream namespace/id, display/local names, nullable metrics |
| `capability_checks` | subject_id, feature, support/availability, reason, evidence time/provenance |
| `recording_sources` | account/module scope, source_type, entitlement state/provenance, cursor/checkpoint |
| `events` | source_id, source_key UNIQUE within source, camera_id, captured/discovered times, ingest status, timestamp_quality |
| `media_assets` | content SHA-256, relative_path, mime, bytes, duration, dimensions, created_at, refcount |
| `event_media` | event_id, asset_id, role (original/thumbnail/frame/export), frame_id/offset when relevant |
| `analyses` | event_id, revision, input fingerprint, model digest, schema/prompt version, result JSON, validation status, timings |
| `event_annotations` | event_id, user_id, favourite, note, corrected labels, updated_at |
| `event_search` | FTS index of current safe summary/notes; synchronized on edits/deletion |
| `jobs` | type, payload ref, dedup_key UNIQUE, status, attempt, available_at, lease_until, worker_id, safe error |
| `notification_rules` | version, structured filter/action, schedule, enabled, created_at |
| `notification_devices` | user_id, transport, encrypted endpoint/keys, label, last_test, revoked |
| `notification_outbox` | event/rule/device/channel, revision_kind, idempotency key UNIQUE, status, retry data |
| `control_commands` | actor, target, operation, desired value, idempotency key, accepted/confirmed times, safe result |
| `source_tombstones` | minimal source identity, deleted_at, purpose; prevent unwanted reimport |
| `audit_log` | actor/action/target/result/time; no secrets or private image payloads |
| `coverage_intervals` | source/camera, start/end, state, gap reason; prevents misleading empty-history claims |

`events -> analyses` is one-to-many. Keep current accepted revision explicitly. A content asset may belong to several events; deleting one event must not delete another event's bytes. Derived data follows retention. Minimal tombstones contain no descriptions or thumbnails.

## Job and outbox guarantees

Use at-least-once execution with idempotent writes, not an unsupported claim of exactly-once distributed delivery. Lease/claim jobs inside a transaction. A worker can crash after a network send and before marking success; stable message tags/dedup keys reduce duplicate notifications, but transport-level exactly-once delivery is not guaranteed.

Commit an accepted analysis and its outbox intents together. Reanalysis of an old event does not generate a new phone alert unless explicitly requested. Use separate state transitions for pending, transport_accepted, client_acknowledged (when available), failed and expired. “Delivered” requires appropriately defined client evidence.

## API conventions

Prefix `/api/v1`. JSON contracts use snake_case; timestamps are ISO 8601 UTC. Generate OpenAPI from backend models and frontend types from the generated contract. Paginate with opaque cursors. All endpoints except minimal health/login/bootstrap require an authenticated session.

Errors have `{code, message, retryable, retry_after_seconds, correlation_id}`; safe messages only. Use 401 for app sign-in, 403 for forbidden, 409 for state conflict, 422 for invalid inputs, 429 for app throttling, and 503 for temporarily unavailable service. A Blink reauth requirement is a domain error rather than logging the user out of Porchlight.

## Routes to implement

| Method/path | Contract |
|---|---|
| `GET /health/live` | Minimal process liveness; no inventory or secrets |
| `GET /api/v1/health` | Authenticated component health, last successful sync, queue/space summary |
| `POST /api/v1/setup/claim` | One-use bootstrap token -> first local owner; loopback-only until claimed |
| `POST /api/v1/auth/login` / `logout` | Local app session, rotate on login, revoke on logout |
| `GET /api/v1/auth/session` | Current user + CSRF/session metadata safe for UI |
| `POST /api/v1/integrations/blink/auth/start` | No-log email/password input -> challenge or connected status |
| `POST /api/v1/integrations/blink/auth/verify` | No-log challenge/code input -> safe state |
| `GET /api/v1/integrations/blink/status` | Auth, capabilities, entitlement evidence, next eligible sync |
| `POST /api/v1/integrations/blink/sync` | Coalesced sync request -> 202/job or cache explanation |
| `GET /api/v1/cameras` / `/{id}` | Cached inventory, metrics, capture ages, capability states |
| `POST /api/v1/networks/{id}/arm` | Explicit `{armed: boolean}` + Idempotency-Key -> command record |
| `POST /api/v1/cameras/{id}/motion` | Explicit enabled state, capability check, audit/read-back |
| `POST /api/v1/cameras/{id}/snapshot` | Supported on-demand operation -> job; no auto-loop |
| `GET /api/v1/events` / `/{id}` | Cursor, filters, safe summaries, analysis/media status |
| `PATCH /api/v1/events/{id}/annotation` | Favourite, note, user-corrected labels, revision conflict handling |
| `POST /api/v1/events/{id}/reanalyze` | Queue a revision; no alert by default |
| `POST /api/v1/imports` | Authenticated multipart upload with limits -> event/job |
| `GET /api/v1/media/{asset_id}` | Authorized bytes with Range/HEAD, no raw filesystem path |
| `GET /api/v1/media/{asset_id}/thumbnail` | Implemented authenticated local JPEG preview from archived media; bounded FFmpeg extraction, private derived cache and no-store browser response |
| `POST /api/v1/events/{id}/export` | Original or labelled derivative; optional redaction policy |
| `DELETE /api/v1/events/{id}` | Local deletion only, cancel jobs, derivatives + tombstone policy |
| `POST /api/v1/search/interpret` | Text -> validated search-query DTO; no SQL execution |
| `GET/PUT /api/v1/notification-rules` | Versioned validated rule collection |
| `POST /api/v1/notifications/devices` | Auth + CSRF; safe endpoint validation and explicit opt-in |
| `DELETE /api/v1/notifications/devices/{id}` | Revoke device delivery registration |
| `POST /api/v1/notifications/test` | Synthetic test tagged clearly; delivery status separate |
| `GET /api/v1/ollama/models` | Backend-discovered local model metadata only |
| `POST /api/v1/ollama/test` | Synthetic vision/schema test; never automatic real-image upload |
| `GET/PUT /api/v1/settings` | Nonsecret settings, revision/version validation |
| `POST /api/v1/retention/preview` / `apply` | Preview and explicit local retention action |
| `GET /api/v1/stream` | Authenticated SSE with bounded replay/Last-Event-ID |
| `POST /api/v1/cameras/{id}/live` | M7 only; guarded session start, never fake live |
| `DELETE /api/v1/live/{session_id}` | M7 cleanup/release |

Backup/restore begins as local CLI functionality, not a remotely callable filesystem-write API. Model downloads also begin as explicit local actions rather than an unrestricted network/download endpoint.

## Media, SSE and access control

Range/HEAD requests must authorize exactly like full file GET. Validate one-range support initially and return correct 206/416 headers. Never expose media through an unguarded static mount. Enforce allowed asset role/type and path containment.

SSE carries event IDs and safe state changes, not source URLs or image bytes. On a replay gap send a resync marker so the client re-queries the API. UI reloads read durable state; SSE is not the source of truth. CSRF and Origin/Host protections apply to control endpoints and notification registration.

## Implemented local live Library — migration 0005

`live_captures` stores owner-requested `recording`/`snapshot` captures independently of Activity events and media-asset deduplication. Fields: UUID, camera ID/name, capture kind, recording/saving/ready/failed state, local save time, bytes, duration (video only), dimensions, SHA-256 and safe failure message. Paths are derived from validated UUIDs inside `media/live-library/`; they are not client-supplied. Staged complete MP4 segments or JPEG input can be finalized after restart; only validated completed captures are playable. Live-session status includes its current recording state.

| Implemented endpoint | Boundary/behavior |
|---|---|
| `POST /api/v1/live/{session_id}/record` | Auth + CSRF + initiating session + fresh attached stream; creates one bounded local recording |
| `POST /api/v1/live/{session_id}/record/stop` | Auth + CSRF + initiating session; idempotent capture finalization without stopping live view |
| `POST /api/v1/live/{session_id}/snapshot` | Same capture boundary; bounded JPEG body from displayed frame, native validation/re-encoding, one per second |
| `GET /api/v1/library` | Owner auth; 30-item cursor pagination ordered by local save time/ID |
| `GET /api/v1/library/{capture_id}` | Owner auth; persisted capture status |
| `GET/HEAD /api/v1/library/{capture_id}/media` | Owner auth, ready-state/path checks, video MP4 or JPEG; protected Range handling |
| `GET /api/v1/library/{capture_id}/thumbnail` | Owner auth; protected saved JPEG/generated recording preview |

These controls do not issue Blink cloud-record commands or alter recording subscriptions. Local live captures support favourites, confirmed deletion and explicitly previewed optional retention. They do not enable automatic AI.

## Current implementation additions — migrations 0006–0013

The initial route table above describes the target contract. The generated [OpenAPI contract](../apps/web/openapi.json) is authoritative for implemented route names. SSE is implemented with bounded authenticated invalidations and guarded polling fallback.

- `0006`: local camera metadata, owner correction, deletion journal and tombstones.
- `0007`: notification rules/intents/inbox; GET/POST `/notification-rules`, PUT/DELETE `/notification-rules/{id}`, GET `/notifications`, POST read/test/snooze. Rules are bounded to 50; deletes keep existing inbox entries.
- `0008`: Library favourites and preview-gated retention; POST `/retention/preview` and `/retention/apply`.
- `0009`: typed saved archive views and stable UUID deep links.
- `0010`: explicit `video/mp4`/`image/jpeg` assets; raw authenticated `/imports` bodies, 256 MiB MP4/32 MiB JPEG limits, protected GET/HEAD/Range.
- `0011`: transactional FTS5 trigram event index, literal operator-safe substring queries.
- `0012`: push-device metadata and per-device delivery; GET `/push`, POST `/push/configure`, POST `/push/devices`, DELETE `/push/devices/{id}`, POST `/push/devices/{id}/test`. Keys/endpoints stay in a separate DPAPI vault. Optional native encryption remains untested.
- `0013`: manual camera command audit; POST `/cameras/{id}/commands`, GET `/camera-commands/{id}`, GET `/cameras/{id}/commands/latest`, POST `/camera-commands/{id}/verify`. UUID idempotency, session/CSRF/capability checks and remote read-back replace optimistic control state.

All paths in this list use `/api/v1`. Additional implemented routes: GET `/integrations/blink/local-recordings`, POST `/integrations/blink/local-sync`, GET `/diagnostics/export`, GET `/ollama/resources`. Local recording jobs carry distinct source type and opaque source IDs; module manifest/prepared-transfer state is excluded from portable backups. Diagnostics and shared-model occupancy are read-only and owner-authenticated.

## Implemented history, state updates and evidence · 2026-10-07

Migration0014 adds permanent historical flags to events/references and independent scan generations/range metadata. POST `/api/v1/integrations/blink/history` accepts `{action: start|pause|resume, days: 0|7|30|90|365}` under owner auth/CSRF. GET recording status includes historical counts/state separately. CAS on generation/page rejects stale discovery completions. Restored Blink events become historical and all restored scans/automation stay paused.

Migration0015 adds a transactional, bounded `state_changes` log. GET `/api/v1/stream` requires a live owner session and emits `change`/`resync` events with an opaque boot epoch/sequence and allowlisted topic names only. Last-Event-ID replay batches 128 rows; retention is 512. Invalid/future/gapped/previous-boot cursors resync. Session validity is checked every second; revocation emits `session_expired`. Capacity: 16 total connections, 4 per session, 300-second connection lifetime, 15-second keepalive; shutdown closes active connections. Restore clears invalidations. This follows the [HTML event-stream protocol](https://html.spec.whatwg.org/multipage/server-sent-events.html); fixture/native browser tests cover import invalidation with polling disabled and session revocation.

AnalysisView includes preset and current-version evidence frame IDs/offsets. GET `/api/v1/events/{event_id}/analysis/{revision}/frames/{frame_id}` regenerates and hash-verifies a private JPEG without persistent storage. Owner/session/Host/Origin boundaries and no-store apply. Invalid IDs/revisions fail; mismatched legacy/version/media results cannot masquerade as accepted input.

Health includes independent checks, last observed success, loop heartbeat, safe synthesized error/action and queue counts. EventView includes allowlisted latest-accepted object categories; listing loads these in one bounded batch. Activity dates use captured time or explicitly labelled discovery fallback; API cursor ordering remains unchanged. Generated `apps/web/openapi.json`/TypeScript remain the authoritative callable contract.


## Implemented owner object labels · migration0016

PUT `/api/v1/events/{event_id}/labels` accepts `{revision, based_on, entities}` under owner auth/CSRF. `entities` is null to restore AI labels, an empty list to explicitly label no objects, or at most 20 controlled category/type/colour/action/direction objects. Actions are bounded to six unique allowed values; subtype must match its category. The expected correction revision is checked in a write transaction; conflicts return409. `based_on` optionally identifies the actual accepted AI revision reviewed by the editor and must belong to this event. Saving later cannot silently change that provenance to a newer AI revision.

Event fields keep owner labels, generated label wording, revision, basis and update time separately. Accepted analyses/frame evidence remain untouched, reanalysis preserves the correction, and editing labels never creates an inference job or new notification. EventView exposes the correction, original AI summary and `labels_source`. Archive chips, same-entity category/colour/direction/action filters and deterministic digests use owner labels where supplied, otherwise the latest accepted AI observation. Digest highlights identify owner versus AI wording; analysed counts still count inference status. Literal search indexes owner label wording alongside notes and original/corrected descriptions. Retention/local deletion and stopped backup/restore include the correction data; diagnostic exports exclude it.

GET `/api/v1/events/{event_id}/match` returns the current EventView or null using the same EventFilters as listing. It is authenticated and allows a loaded older row to refresh or disappear after an edit/deletion without replacing the archive's other pages. Cursor appends deduplicate IDs; dialog focus and scroll position survive editing.

CameraRecording now includes the latest recording's effective summary, `summary_source` (owner/ai/none) and `analysis_status`. Selection still orders by captured time, with discovery fallback. GET `/api/v1/cameras/{camera_id}/commands/latest` accepts optional `operation=network_armed|motion_enabled` so separate network and motion controls retain their own last result; unsupported values fail validation and authentication remains required.

Migration0017 adds `notification_rules.revision`, starting at1 for existing rows. RuleView exposes it. POST still accepts RuleBody; PUT requires RuleUpdate with `definition` and `expected_revision>=1`. DELETE requires the `expected_revision` query parameter. Both serialize a compare-and-change inside `BEGIN IMMEDIATE`; stale revisions return409 `RULE_CONFLICT`, missing rows404. Each successful edit increments the revision; creation and listing do not generate notification intents.
