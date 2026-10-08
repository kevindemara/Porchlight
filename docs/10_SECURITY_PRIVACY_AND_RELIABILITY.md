# 10 · Security, privacy and reliability

## Threat model

Protect Blink account access, home-camera footage, derived observations, local app sessions and device notification endpoints. Threats include a malicious website targeting a loopback service; an untrusted LAN user; leaked tokens/logs; an imported malformed media file; a compromised dependency; prompt injection visible in camera imagery; a lost phone; and ordinary crashes, sleep or disk exhaustion.

An OS administrator or malware running as the same Windows user can defeat many local protections. Do not describe OS-bound secrets as invulnerable or claim the application encrypts footage when it only encrypts credentials.

## Secrets

Use a reviewed Windows DPAPI/OS-vault implementation through a narrow `SecretStore` interface. Bind the secret envelope to the intended service user's identity. Store raw session/refresh material only encrypted; clear transient passwords/2FA from application structures as soon as practical, without claiming guaranteed Python memory zeroization.

No credentials in `.env`, command arguments, Git, frontend bundles, browser localStorage, metrics, exceptions or screenshots. `.env.example` contains only nonsecret configuration. Exported diagnostic bundles exclude secret files and strip signed URLs, cookies, request bodies, account IDs and auth headers.

Reusing a user-bound vault under a different Windows account may fail by design. Restore the application data, then reauthenticate; do not “fix” this by saving the password in plaintext. A portable encrypted recovery export is a separate explicit feature with reviewed cryptography.

## Application access

Bootstrap is loopback-only and protected by a single-use expiring token. Disable setup claiming after the first administrator exists. Require a strong local password stored with a modern password-hashing implementation, login throttling, and revocable sessions. Use secure HTTP-only SameSite cookies over HTTPS; allow a clearly scoped localhost-only development cookie exception where necessary.

Enforce allowed Host values to limit DNS-rebinding attacks, explicit Origin checks, no wildcard CORS, CSRF tokens on authenticated state changes, and auth on all media including thumbnails, Range/HEAD and live manifests/segments. Destructive actions need explicit UI confirmation. Prefer POST/DELETE rather than state-changing GET endpoints.

Validate headers and proxy trust; only honour forwarded headers from configured local proxies. Do not bind the service to all interfaces during first-run setup. Never expose a raw Ollama port through a reverse proxy or public tunnel.

## Inference isolation and prompt injection

Camera images, notes and clip metadata are untrusted. Instructions seen on signs or screens inside images have no authority. Keep the vision worker without tools, credentials, arbitrary URL fetch or control APIs. Treat all model output as untrusted until schema and semantic validation complete. Escape it in UI; never render model-generated HTML.

The natural-language search model returns typed query fields; application code enforces time ranges, camera access and parameterization. It cannot generate executable SQL, filesystem paths or API calls. Models may describe activity but cannot arm/disarm, send emergency requests or activate hardware.

Strict local AI is validated before private-image inference. No silent cloud fallback. Development is a separate boundary: never commit or upload real footage to cloud coding agents just because the application runtime is local.

## File and network safety

Allow known media types and bound bytes, duration, dimensions, frame counts and processing time. Ignore supplied filenames for storage paths. Validate real path containment and refuse traversal/symlink escape. Use generated names and atomic moves. FFmpeg runs without shell interpolation and without remote/network media inputs; kill timed-out child process trees.

Blink-origin download URLs require a provider-owned validation policy and credential-safe redirect handling. Never forward auth headers to an untrusted redirect target. An expired signed URL triggers a controlled fresh lookup, not a log dump. Web Push and optional webhook/ntfy destinations have separate allowlists and SSRF protections.

Do not create a “download any URL” endpoint. Uploaded media never becomes a plugin, HTML page, or script. Keep scratch files out of the public static directory.

## Data privacy and retention

Local archive media is protected by app authorization and OS filesystem permissions. Whole-disk encryption is a separate user/device configuration; report its status only when detected, without silently enabling it. Optional encrypted archives require deliberate design, not a misleading lock icon.

Delete source event descriptions, thumbnails, frames, analysis revisions, search/embedding entries and pending notifications with the event. Minimal dedup tombstones are disclosed. Already exported files, system backups and phone notification history are separate copies; do not promise instantaneous erasure everywhere.

Backups include a manifest of included personal data. Never automatically sync footage to OneDrive, Google Drive or a hosted object store. Audio analysis and demographic inference remain out of scope. Owner-named face recognition is optional and local; SFace templates stay in a Windows DPAPI envelope, and unknown faces remain visible without a name.

## Reliability design

Persist jobs before execution; leases and idempotency recover after crashes. Retain downloaded recordings even when AI fails. Reconcile files/DB at startup, detect missing media, and never silently mark a corrupted file available.

Reserve free disk space, preview cleanup, protect favourites and pause ingestion on low space when cleanup cannot safely recover. Default: 30-day ordinary-media retention and a configurable 50 GiB soft archive budget, with at least 5 GiB reserve; this is a starting policy the owner approves, not an unconditional deletion command. Pinned data can force a pause rather than deletion.

Old backfills do not spam notifications. Scheduling uses monotonic timers for waits and UTC for persisted timestamps; reconcile missed intervals after sleep without inventing observations. Keep bounded logs and expose stale worker/source/model health.

## Required negative tests

Unauthorized media/Range access; hostile Host/Origin; missing CSRF; replayed bootstrap; brute-force login; unsafe push endpoint/redirect; path traversal; malicious filename; invalid MP4; enormous dimensions; model output containing HTML/tool requests; visual prompt injection; expired Blink session; disk full; crash after media rename; crash after push send; duplicate source event; and secret leakage through every diagnostic/export path.

Before release, review current dependency advisories and licence notices. No testing shortcuts that disable TLS checks, open the firewall, print secrets or eliminate authorization.
