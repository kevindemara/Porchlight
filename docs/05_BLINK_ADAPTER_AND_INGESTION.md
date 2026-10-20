# 05 · Blink adapter, authentication and ingestion

## Integration contract

All external Blink behaviour stays inside `providers/blink/`. Public-domain DTOs must not expose upstream credential objects or signed media URLs. Authenticate with the owner's account only. Keep a stable installation/device identifier where required by the library; do not randomly replace it at every restart.

The reviewed library exposes cloud metadata/download operations and a separate local-storage implementation. Treat their behaviour as version-specific. Do not assume a bulk cloud-download helper also covers every local clip. [R3–R4](15_SOURCES_AND_VERSIONING.md#r3)

## Authentication state machine

`not_configured -> authenticating -> challenge_required -> verifying -> connected`

Failure states: `invalid_credentials`, `challenge_expired`, `reauth_required`, `rate_limited`, `service_unavailable`.

Setup starts on loopback with a one-time, expiring bootstrap token printed only to the local console; consuming it creates the local administrator. Bind account setup to that authenticated local session. The form accepts Blink email/password through a no-log request, then the genuine verification-code challenge. Do not invoke blocking terminal prompts from the web request handler.

Inspect the pinned library's actual auth exceptions and methods instead of copying old tutorials. Translate them to our auth-challenge response with opaque challenge ID, expiry if known, delivery method if known, and safe UI text. Codes and passwords are never returned.

Persist only session material actually needed, in an encrypted OS-backed envelope. Avoid retaining the password after successful session establishment; if the library truly requires it, keep it encrypted and disclose that to the owner. Never persist 2FA codes. Use a single-flight token refresh. On a real reauth requirement stop polling and ask through the app; do not repeatedly log in or resend codes.

## Inventory and capabilities

Identify an account, network, module, and camera by stable upstream identifiers, not display names. Include device family in identity when different device namespaces can reuse numeric IDs. Local names are independent. Two cameras may have the same label.

Capability values have a support state, reason, checked time, and provenance. Read-only discovery does not certify write actions. Keep nullable metrics nullable. Do not convert battery “ok/low” to an invented percentage or a stale sync module heartbeat into proof that every camera is online.

Classify each recording source separately: `blink_cloud`, `blink_local`, `manual_import`, `demo`. Record entitlement evidence as `api_reported`, `owner_confirmed`, or `unknown`. A failed cloud listing is not evidence of a no-plan account.

## Scheduling policy

Routine cloud clip discovery defaults to **60 seconds**, with up to five seconds of positive jitter. Background account inventory, historical retrieval and Sync Module discovery retain their **120-second** pace. These are app defaults, not official API limits or a guaranteed safe rate. The library README discourages calls faster than 60 seconds. [R1](15_SOURCES_AND_VERSIONING.md#r1)

`PORCHLIGHT_CLOUD_POLL_SECONDS` can override only routine cloud discovery (30–3600 seconds). A 30-second value is an explicit temporary testing option below the library's recommendation, not the default. Errors keep at least 120 seconds of exponential backoff and respect longer Retry-After values. Known temporary listing, transfer and rate-limit failures recover automatically: after four attempts, wait at least 15 minutes before another bounded retry cycle. Enabled work left failed by an earlier version is recovered with the same cooldown. Authentication, changed contracts, configuration problems and expired media are not automatically revived. Pausing a source also pauses its recovery. Changing cadence after restart can bring forward healthy queued routine discovery, but must not accelerate error retries or historical/module work. Serialized work, downloads and Blink clip availability can add latency beyond the nominal interval.

One account scheduler coalesces work for all open UI clients; opening five tabs must not quintuple API traffic. A module manifest refresh is one coordinated workflow, not one request per camera. Track actual HTTP request counts because one library refresh can issue many underlying requests.

Short internal polls required to complete an upstream command/manifest workflow are different from starting new discovery cycles. Preserve verified library pacing, cap workflow duration/attempts, honour rate-limit responses, and do not override throttles with forced refresh in production. Manual commands enter the same account scheduler. A Refresh button can return cached state with a next-eligible-sync timestamp.

Use exponential backoff with jitter for transient failures, respect Retry-After, and pause on auth failures. Default to no periodic snapshot wakeups; derive dashboard previews from ingested clips where possible. Do not poll by constantly requesting new camera captures.

## Cloud discovery

Inspect the pinned implementation's metadata iterator/pagination. Page through the configured discovery window, persist every clip reference in a transaction, and only then commit the page cursor/checkpoint. Track a bounded overlap window for out-of-order and delayed events. On backlog overflow expose an incomplete-coverage indicator and a resumable backfill job.

Enumerate until a safe checkpoint is reached, not merely a hardcoded first ten pages. Cloud clip IDs, camera IDs, captured timestamp and source mode form a durable identity. Source URLs are transient retrieval locators, never primary keys or client-visible permanent links.

## Local-storage discovery and download

Implement a distinct asynchronous workflow:

1. Ask the module for a new manifest when eligible.
2. Wait/poll through the pinned adapter's supported completion mechanism; handle busy/timeout without restarting every tick.
3. Normalize all manifest entries and persist discovery records.
4. For each missing local clip, request whatever transfer/preparation the supported API requires.
5. Wait for readiness, then download the actual media; validate it before marking the event available.
6. Recover when the manifest generation changes, the module restarts, removable media is absent, or a clip disappears.

Use one active workflow per module. Manifest IDs may be ephemeral and are not sufficient durable clip identity. Prefer a stable source clip ID plus account/module/camera/capture time, including storage-volume generation where available. When the upstream identifier is not stable enough, document the composite identity and use the downloaded content hash as a second dedup layer.

The library's reviewed local code processes manifests and prepares clip transfers, while cloud helpers have their own path. Codex must verify the actual installed code and build contract tests, rather than presume one high-level function is a reliable universal downloader. [R3–R4](15_SOURCES_AND_VERSIONING.md#r3)

## Durable ingest and event lifecycle

`discovered -> download_queued -> downloading -> media_ready -> analysis_queued -> analyzed`

Independent branches include `metadata_only`, `download_retry`, `media_expired`, `analysis_failed`, `analysis_skipped`, and `deleted_local`. A failed analysis never changes `media_ready` back to missing.

Download to a generated `.part` filename in the destination filesystem. Stream to disk with byte and timeout limits, validate file signature/decodability, calculate SHA-256, then atomically rename. Persist content metadata and the next job transactionally. On startup reconcile orphan partial files and completed files not yet committed. Never trust a URL's `.mp4` suffix or an HTTP 200 error page.

Use stable source-key uniqueness for events and content-hash addressing for assets. Byte-identical content can be shared physically while distinct source events remain distinct; do not collapse different camera/time events solely because their bytes match. Manual imports use a separate namespace and are idempotent by content + chosen event association.

Handle timestamps explicitly. Preserve raw source time, normalized UTC time, timezone provenance and timestamp quality. Naive/ambiguous times need a documented interpretation or owner correction; no silent timezone substitution. Do not substitute download time as camera capture time without marking it estimated.

## Retention and tombstones

Deleting a local event/media copy must not trigger upstream deletion. Keep a minimal source-key tombstone so the same clip is not downloaded again on every sync; disclose this in deletion settings. Full source-key erasure is a separate option that warns about possible reimport. Remove derived frames, descriptions, search entries and queued notifications for deleted events. Share physical media assets safely using reference counts.

## Diagnostics and error handling

Normalize safe errors: `AUTH_REQUIRED`, `RATE_LIMITED`, `SOURCE_UNAVAILABLE`, `CAPABILITY_UNSUPPORTED`, `MEDIA_EXPIRED`, `INVALID_MEDIA`, `DISK_FULL`, `UPSTREAM_CHANGED`. Include retryable, next retry time, correlation ID and safe owner action. Never return raw upstream bodies, account identifiers, signed URLs or tokens in public errors.

A “connection successful” indicator means authentication/inventory succeeded, not that local clips, AI, live view, and phone notifications all passed. Track them as separate tests.
