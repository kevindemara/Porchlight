# blinkpy adapter intake

Pinned dependency: blinkpy 0.25.9, MIT, from [fronzbot/blinkpy](https://github.com/fronzbot/blinkpy). Its installed source and coroutine signatures were inspected on 2026-10-06. Only `services/porchlight/providers/blink/` imports it. No upstream application source was copied.

| Interface used | Purpose and boundary |
|---|---|
| `Blink(refresh_rate=120, session=...)` | One serialised account actor and shared aiohttp session |
| `Auth(data, no_prompt=True, session=...)` | Local UI supplies credentials; no interactive terminal prompts |
| `Auth.startup()` / `BlinkTwoFARequiredError` | Initiate legitimate owner login and expose a bound, expiring local challenge |
| `Auth.complete_2fa_login(twofa_code)` | Verify code with Blink; maximum five local attempts |
| `Auth.login_attributes` | Persist reusable session material after removing password/code |
| `Blink.setup_urls()`, `Blink.get_homescreen()` | Read inventory only; do not call the full platform startup that may perform additional operations |
| `api.oauth_refresh_token(auth, refresh_token, hardware_id)` | Refresh saved sessions without falling back to a stored password |
| `Auth.need_refresh()` | Decide whether an explicit token refresh is needed |
| `api.request_videos(blink, time=..., page=...)` | Complete paginated cloud discovery; no dependency on the high-level helper's default ten-page ceiling or latest-video cache |
| Shared authenticated `ClientSession.get` | Stream an inspected relative cloud locator into bounded local storage; exact REST origin, no automatic redirects, credential forwarding or signed-query persistence |

Stable camera identifiers use an encrypted installation namespace plus upstream family/id, independently of display names. Sanitized inventory is cached in SQLite. Network arm/motion state is observed metadata; supported manual commands now use persisted pending/unknown outcomes and refreshed read-back. Refreshes are coalesced to at least two minutes; new sign-ins have a one-minute cooldown. API loggers that could emit raw account material are disabled. Redirected/signed-media handling is not implemented in this slice.

Tests exercise installed signatures, synthetic auth/inventory, Windows DPAPI, cloud normalization, multi-page discovery, durable jobs, retries/leases, decoder validation and authenticated playback. Cloud pages are committed with their references/download intents before advancing the page cursor. Completed scans retain the incremental checkpoint, but each new ordinary cloud scan reconciles at least the previous 24 hours: native investigation found today's available clips behind the older five-minute overlap. Stable source keys deduplicate the wider listing. Failed/incomplete scans keep their original since/page; historical ranges and Sync Module manifests are unaffected. HTTP trace handling honors provider 429 delays and counts actor requests without logging URLs or bodies.

The owner reported real login and camera connection. One doorbell is cached, and its inventory was refreshed during the latest actual app restart (0.1 s before the new process record); this supports real session restore/inventory validation without exposing account IDs or credentials. The owner confirmed paid-cloud recording import and playback. Newly created no-plan recordings and Sync Module transfer remain **NOT RUN**. The owner confirmed an active paid plan and packaging identifies Sync Module Core. No automatic camera actions or subscription changes are performed. Experimental live transport and manual controls are capability-gated; see [LIVE_VIEW.md](LIVE_VIEW.md).

## Additional candidate operations — inspected 2026-10-07

The adapter uses pinned `api.request_local_storage_manifest`, `api.get_local_storage_manifest` and `api.request_local_storage_clip`, then its same strict authenticated REST transfer implementation. All operations hold the account actor. Module/API reports must identify compatible enabled active local storage; the current Core is ineligible. Manifest polling is bounded, incomplete/malformed manifests do not advance checkpoints, and durable prepared-transfer intents attempt GET before repeating a POST after interruption. Source keys are account/module/clip/time/size based, independent of manifest request generation; opaque camera-name matches must be unique. Source provenance is `blink_local`, separate from paid-cloud queues. Missing prepared bytes are retryable; a clip absent from a complete manifest may be marked expired. No storage-volume generation is verified, so card replacement/reformatting and ID reuse are acceptance gates. API fixture success is not evidence of XR+/XR/2 compatibility or no-plan retrieval.

Manual network commands use `api.request_arm`/`request_disarm`; motion uses `api.request_motion_detection` for the pinned supported family mapping. The adapter refreshes/reselects the camera and checks the initiating session again immediately before mutation. Timeout, interrupted execution or unmatched read-back remains unknown; only a read-only refresh follows. No owner arm/disarm or motion setting was changed during unattended work.
