# Changelog

## Every saved face profile on first load · 2026-10-08

- Show every saved person on the Faces page immediately, with up to three representative labeled crops from the saved scan library. Older-scan pagination now adds review detections without hiding names that occur only in older recordings.

## Named faces first · 2026-10-08

- Show saved-person cards before unidentified appearances in the Faces gallery, including after loading older scans. Keep the existing order within each section.

## Library-wide named-face counts · 2026-10-08

- Show each saved person's owner-confirmed detection count across every saved scan, separately from automatic model matches and the faces grouped in loaded gallery pages. The count updates immediately after bulk approval and remains accurate after refresh.

## Larger reviewed-face approvals · 2026-10-08

- Allow up to 1 MiB of JSON on the authenticated suggested-face approval route so a reviewed group of 203 faces can be labeled in one atomic request. Keep the ordinary 16 KiB request limit and the route's 2,000-face validation cap; oversized approval requests still fail with 413.

## Grouped suggested face review · 2026-10-08

- Gather individually unlabeled faces under possible saved-person names in a separate Faces-page review area. Load all saved scan pages with one action, inspect source clips, and set aside any image that does not belong before approving the rest together.
- Make approval an authenticated, atomic report-labeling action, independent of the 12-image enrollment batch and 32 training-sample cap. Stale reports, frame hashes or face boxes reject the whole action. Set-aside images remain unnamed; they can be restored during the current review and may be suggested again later.

## Full Activity face backfill and older-results browsing · 2026-10-08

- Scan the 128 saved Activity recordings that did not yet have accepted face reports, in a bounded local queue. Together with 21 existing current-policy reports, all 149 saved recordings now have v3 face reports; no jobs failed.
- Page the Faces gallery by recording date so older scans remain reviewable after a full-library backfill. Load older detections on demand and combine repeated named-person cards across pages.

## Faces page, review gallery and larger profiles · 2026-10-08

- Move optional face detection and recognition controls to a dedicated **Faces** navigation page. Show authenticated, on-demand crops of up to three clear examples per tentative group so the owner can name a person or add a sample.
- Increase the per-person limit from eight to 32 samples. Preserve new SFace exemplars separately, including a legacy profile's former average, so different poses are available to future comparisons.
- Add an explicit **Rescan recent 20 videos** action and a bounded gallery across recent reports. On this PC, the latest owner-requested rescan completed for all 20 saved videos with no failed jobs; its 701 sampled frames yielded 67 face detections, including 14 model-suggested labels and 13 preserved owner labels. These counts do not establish identity accuracy.
- Select up to 12 images across gallery cards and assign them together to a new or saved person. Suggest a possible existing name for close but inconclusive matches, leaving the assignment to the owner.
- Add a separate automatic-sample switch for future scans. It requires eight owner-assigned examples, two clear strong matches in one clip and rechecks the selected face against manual exemplars; one nonduplicate sample per person/clip can be added. Thresholds are engineering heuristics, not calibrated certainty.
- Preserve owner-assigned face labels across a rescan when the same hashed frame contains a matching face box, even if the new automatic suggestion differs.

## Denser face sampling and detector sensitivity · 2026-10-08

- Increase face detection from about one to four sampled frames per second on short clips, capped at 48 per clip. Lower the YuNet score cutoff from 0.90 to 0.80 after aggregate-only local diagnostics found moving candidate boxes below the old cutoff. Keep older reports readable and rerun with the v3 policy when requested.
- Keep the separate Qwen evidence strip unchanged; its three displayed frames are for scene description, not the face detector.

## Clearer no-face result · 2026-10-08

- Explain that a visible person can still yield no detectable face, especially when turned away, distant or between samples. Point to the owner description for that clip and a clear-face recording for future SFace recognition.

## Recognized names in Activity analysis · 2026-10-08

- Show saved SFace names as possible matches on Activity cards, beside the recording description and inside its analysis panel, with the local recognition source made explicit.
- Resolve names when Activity loads so profile renames/deletions take effect immediately without changing Qwen's stored description. Label the sampled clip as soon as the owner saves its face; other prior clips can be detected again.
- Verify API lifecycle and synthetic four-viewport Activity rendering; real identity accuracy still needs owner-reviewed footage.

## Compact Settings columns · 2026-10-07

- Stack each desktop Settings column independently so short panels do not inherit a taller neighbor's empty row space.
- Keep the existing panel/keyboard order and mobile single-column layout; resize observation adjusts spacing as status text or help expands.

## Optional local face detection · 2026-10-07

- Add a separate YuNet CPU detector for sampled face counts, timestamps and size/sharpness flags. No identities, enrollment, embeddings or demographic output.
- Add recording-detail requests and a default-off automatic setting for new recent Blink clips, independently of Qwen descriptions.
- Preserve original clips and prior accepted results on failure; bound/recover jobs, protect active media, remove reports on deletion and pause automatic detection on restore.
- Install the optional exact packages and verified external model after owner approval. Retain notices, advisory intake and setup instructions; core bootstrap remains independent.
- Verify generated-media native inference and four-viewport UI flows. The newest real saved camera clip completed 10 samples in 1.86 seconds with no detected faces; visual accuracy remains an owner check.

## Approved porch-light branding · 2026-10-07

- Apply the orange/amber lamp, camera lens and viewing-cone mark to setup/sign-in, loading, desktop sidebar and mobile header.
- Update browser-tab, home-screen and notification icons with versioned standard-size assets and a maskable export.
- Retain the approved original; export icon sizes with existing FFmpeg and verify public asset serving, desktop/phone layout, manifest and offline behavior.

## Automatic AI hardware evidence and keyboard navigation · 2026-10-07

- Verify four newly retrieved owner cloud clips completed automatic native local AI, with accepted revisions, four to six frames and preserved originals. Recorded analysis durations:31.53–50.02 seconds; visual accuracy still requires owner review.
- Fix the keyboard Skip to content link so it focuses the current main region without changing the hash route or resetting the page. Add a six-page keyboard/filter regression at all four viewport widths.

## Activity thumbnails and immediate automatic AI · 2026-10-07

- Contain thumbnails inside their fixed desktop/mobile dimensions, centered within Activity rows; image intrinsic dimensions no longer overflow the card.
- Signal the AI scheduler after a cloud/local clip is durably archived. Keep scheduling independent of the serial inference worker, coalesce arrivals and retain a 30-second recovery scan.
- Wake scheduling on settings changes. Preserve explicit opt-in, the tested local-only model gate, bounded queue, silent history/manual imports and original recordings when AI is unavailable.
- Enable automatic AI on the owner's explicit request using the already installed/tested Qwen model in Balanced mode, for newly discovered recent clips. Older recordings remain on request.
- Test cloud and local arrival while inference is held busy, disabled-AI archiving, worker cancellation and real generated-video thumbnail containment at four viewport widths.

## Automatic cloud sync reconciliation · 2026-10-07

- Recheck at least the previous 24 hours when starting a new routine cloud scan, so available clips behind the incremental checkpoint are discovered. Preserve interrupted pagination, older initial coverage, explicit history, retries and source deduplication.
- Recover four of today's owner recordings automatically after the fix, increasing the native archive from132 to136 without enabling AI or changing the Blink camera.
- Add a generated-video regression where a three-hour-old clip becomes visible after the first completed scan; assert successful archiving and no duplicate events/downloads on repeated scans.

## Source portability and clock recovery · 2026-10-07

- Test copied runtime source, migrations, prompts, schemas and built assets with the existing installed interpreter, a path containing brackets/spaces and isolated synthetic data. Verify native startup, sign-in, video import, private playback/thumbnails and restart.
- Recover interrupted recording and unaccepted AI jobs promptly after a backward clock correction. Preserve queued provider backoff and accepted results; simulate both forward and backward corrections without changing the PC clock.
- Add the release evidence review with explicit hardware, phone, accuracy, installation and licence gates. Correct the limitations text to retain both the earlier Light rejection and later one-clip success.

## Rule conflicts and setup preflight · 2026-10-07

- Add revision-based notification rule edits, enable/pause and deletion. Keep unsaved browser drafts separate from background refresh; explicitly reload/review after a conflict.
- Preserve existing rules at revision1 through migration0017. Simultaneous updates have one winner and generate no notification intents.
- Add read-only `bootstrap.ps1 -Check` and reject incompatible Python/Node before installing. Use literal PowerShell locations so checkout paths containing brackets work.
- Retain three missing exact-version upstream notice files with provenance hashes; one notice gap remains unresolved.

## Camera status, rule scopes and prompt contract · 2026-10-07

- Show the latest saved clip's analysis status and source-labelled effective description on Cameras; expose battery, temperature and observation time without expanding controls.
- Put one network arm/disarm control at each network heading, retaining confirmation and read-back. Keep motion controls per camera and separate command-history queries by operation.
- Add multiple camera/category/colour/direction choices per notification rule, with explicit all-values resets and preserved unavailable camera selections.
- Clarify category/subtype mappings in vision prompt 1.1 without weakening validation. One native Light probe accepted three frames in 36.83 seconds; visual accuracy remains unverified.
- Reject queued jobs whose prompt/extraction/workload contract changed before private inference. Preserve prior accepted revisions and allow a new explicit request.
- Record remaining installed-package notice gaps for release review.

## Large archive review and owner labels · 2026-10-07

- Window long loaded histories with measured variable rows, native scrolling, keyboard access, resize anchoring and dialog return focus. Keep older pages loaded after edits/deletion.
- Add structured owner category/type/colour/action/direction corrections with revision conflicts, explicit empty sets and reset. Preserve the actual reviewed AI revision and all accepted evidence.
- Use effective labels in chips, same-entity filters, literal search and source-labelled digest highlights. Corrections survive backup/restore and generate no new alerts.
- Keep invalid Light inference rejected: native diagnostic reported subtype_mismatch in45.77 s. Footage/raw output remain local; visual accuracy remains an owner gate.

## Guided setup · 2026-10-07

- Add a reusable local setup guide for privacy, storage, Blink, recording source, model workload/test, phone pairing and final observed readiness.
- Preserve failed/unavailable states when skipped; navigation never enables automation or starts live view. Restore focus and the current settings draft on close.
- Link empty Cameras to the guide and remove the false no-camera claim from the signed-out screen. Storage relocation remains an explicit stopped-profile operation.

## History, evidence review and independent status · 2026-10-07

- Add resumable 7/30/90/365-day/all-available historical cloud retrieval, generation-safe stop/resume, fresh-work priority and permanent silent-history provenance; preserve deduplication/backoff.
- Add network/local-group camera arrangement and observed network state, date-grouped newest-first Activity, validated object chips and retrieval coverage warnings.
- Add bounded authenticated SSE invalidations, replay/resync/session-revocation handling and polling fallback; clear replay records on restore.
- Add frozen Balanced/Light AI workload presets, static validation-reason diagnostics and exact checksum-verified sampled-image previews with video seeking/retry. No preview copies accumulate on disk.
- Add independent source/AI/disk/push and real worker-loop readiness, observed last-success timestamps and safe recovery actions.
- Fix Windows venv launcher readiness with per-launch identity and close SSE during cooperative shutdown. Reject mapped network-drive runtime storage.
- Keep owner automatic AI/retention off. Native Balanced analysis accepted five frames; Light failed validation. Accuracy/hardware/phone/release gates remain incomplete.

## Archive workflows, local notifications and recovery · 2026-10-07

- Add recording filters, protected thumbnails, owner description corrections, local camera names/groups, shared-file-aware local deletion and tombstones.
- Add local search interpretation with reviewed filters, deterministic daily digests, saved views and authenticated recording links that survive reload.
- Add transactional in-app notification rules, inbox, read state, quiet hours, cooldowns, expiry and snooze. Phone delivery remains pending.
- Add verified local backup/new-profile restore, excluding secrets/sessions/live trust and pausing restored automation.
- Add optional previewed retention, favourite protection for Activity and Library, explicit capture deletion and consistent reserve/budget checks. Cleanup stays off until confirmed.
- Allow explicit one-clip analysis while automatic analysis is off; measure additional native AI/search tests without exposing imagery.


## Local live captures and Library · 2026-10-07

- Add explicit Record/Stop recording and Snapshot controls to Live view and fullscreen, with capture actions immediately under the video on phones.
- Save bounded video-only MP4s and displayed-frame JPEGs to a protected local Library with camera/save-time labels, playback, viewing and downloads.
- Add migration `0005`, complete-segment capture, validated finalization/restart recovery, storage limits and authenticated/CSRF/session-owner routes. Capture failures preserve live playback and saved Blink clips.

## Live view navigation · 2026-10-07

- Add a dedicated Live view destination to the desktop sidebar and phone navigation, with a camera selector and inline player. Camera cards now focus on saved recordings.
- Preserve explicit start, fullscreen, stop and capability controls; clean up sessions when switching cameras or leaving the tab, including late start responses.

## Live video fullscreen · 2026-10-07

- Add enter/exit fullscreen controls to the live video with an accessible stop button, freshness status and ended/stalled overlays retained while expanded.
- Verify actual browser fullscreen with generated video at all four viewport sizes, including unsupported-browser feedback and cleanup.
- Document the distinction between Porchlight's precautionary one-minute delay and Blink's motion-recording retrigger setting; no shorter live reconnect interval is claimed as hardware-verified.

## Compact Cameras heading · 2026-10-07

- Remove the workspace eyebrow and tagline from Cameras, reduce its title size and tighten the top spacing so previews sit higher on desktop and phone screens.
- Rebuild the served interface and verify existing camera preview/playback checks at all four viewport sizes.

## Development port · 2026-10-07

- Move the local Vite interface to port 5174 and update the backend development-origin boundary and setup instructions, preserving port 5173 for the owner's other application.
- Verify origin isolation with API security tests; the frontend build and local development proxy checks pass.

## Local one-clip AI test · 2026-10-07

Added an explicit newest-clip native AI probe that preserves automatic-AI settings and emits only validated observations or safe metrics. Real inference exposed repeated identical action tags; the validator now canonicalizes exact repeats of allowed actions before schema validation. Unknown actions, malformed types, duplicate entities, unsupported evidence and temporal/colour restrictions remain enforced. A native test against five sampled real frames passed after this change; visual accuracy awaits owner review. The development server is available while testing continues. Phone Web Push/PWA and remote HTTPS support remain future work.

## Camera archive evidence and previews · 2026-10-07

Camera cards show verified recording access when that camera has archived cloud clips, including after inventory refresh. The Cameras page refreshes archive evidence every ten seconds. Added authenticated local JPEG thumbnails from the newest saved clip by recording time, recorded-time captions and click-to-play. Older clips synced later do not replace newer dated previews. Missing thumbnails preserve the playback button. Extraction uses the existing FFmpeg installation and private profile cache; no Blink snapshot requests or AI analysis.

## Experimental live view · 2026-10-06

Added user-triggered video-only live sessions, verified relay transport with complete packet reads, in-memory FFmpeg/browser encoding/playback, owner-session media protection, CSRF controls and cleanup on close, logout, account reconnect, expiry or lost heartbeats. Added fresh-frame LIVE gating, 90-second and byte/backpressure limits, no automatic restart, explicit certificate fingerprint approval/revocation and a sanitized short hardware probe. After owner approval of the exact relay certificate for Porchlight, the actual doorbell delivered 66,328 encoded bytes in a 5.44-second probe. No imagery was saved. Generated-stream browser tests pass; actual camera browser playback is not yet verified.

## Initial local clip analysis · 2026-10-06

Added an independent durable AI queue, bounded FFmpeg frame sampling/deduplication, local-only Ollama policy and model-digest gates, persisted synthetic-test readiness, structured evidence validation and versioned neutral descriptions. New camera clips can be analyzed after explicit opt-in; older history is processed on request. Analysis failures preserve recordings, notes and favourites. Added clip analyze/retry/reanalyze controls, readiness/queue counters and searchable descriptions; cloud archival capability labels now reflect observed archived clips.

The owner confirmed playback of real archived Blink cloud clips. Ollama's no-cloud setting was explicitly approved and applied; the owner restarted the server and its running policy was verified. No new model or dependency was installed. Private-camera analysis accuracy and no-plan/local-module retrieval remain unverified. Browser journeys use isolated profiles per viewport and synthetic AI fixtures.

## Cloud recording sync · 2026-10-06

Added opt-in cloud-to-PC recording sync, persisted pagination/checkpoints and references, serialized download jobs with leases/restart recovery, bounded retries and Retry-After handling. Available clips are streamed to bounded temporary storage, decoded with FFmpeg, journaled and atomically archived independently of AI. Added cloud provenance/camera association, safe pending/failure counters, pause/retry controls and owner-confirmed entitlement settings. No clip deletion or camera write actions are performed.

The owner connected a real doorbell; actual session restoration/inventory refresh survived the updated-app restart. Packaging identifies Sync Module Core, which does not support USB/microSD local storage. Real cloud recording playback still needs the owner's local test; no-plan and local-module retrieval remain unverified.

## Local development 0.1.0 · 2026-10-06

Added the Windows-native FastAPI/SQLite runtime, owner/session/CSRF security, migrations and single-profile process lock; a responsive React interface with generated API types; Windows-encrypted Blink sign-in and inventory adapter; bounded FFmpeg-validated manual imports with protected Range playback, durable recovery journals, notes, favourites and literal search; local-model discovery and a synthetic Ollama vision test. Added pinned dependency locks, licence notices and runnable setup/start/stop/development/test scripts.

Configured a pinned, checksum-verified local FFmpeg/ffprobe installation. Used the existing Qwen vision model successfully with a generated image; no model was downloaded. Real Blink recording retrieval, private-media analysis, notifications, retention and backup/restore remain pending. This is an initial development build, not a completed or camera-validated release.

## Specification package · 2026-10-06

Initial independently written Porchlight product/engineering specification, implementation milestones, source/licence research, Codex project instructions, AI prompts, JSON contracts, synthetic examples and read-only environment preflight.

No application implementation, real Blink connection, local Ollama inference, model benchmark or phone-delivery test was performed in assembling this package. See `PACKAGE_VALIDATION.md` for the checks actually performed.

## Local retrieval candidate, review tools and hardening · 2026-10-07

- Add bounded Sync Module manifest/prepared transfers with a separate durable queue, opaque identity, auth/eligibility gates and explicit setup/pause. Core remains ineligible; real new-module/no-plan validation awaits hardware.
- Add validated JPEG imports and transactional literal FTS5 indexing; retain small local frame changes in the bounded AI sampler.
- Add persisted manual camera controls with session recheck, disable confirmation, read-back and unknown-outcome verification, without unattended hardware writes.
- Add optional Web Push pairing/vault/per-device expiry, retry and unknown-delivery handling. Candidate encryption packages await approval; actual phone display is unverified.
- Add allowlisted diagnostics, configured-storage readiness, persistent AI test readiness and read-only shared Ollama memory status.
- Add rule timezone editing, confirmed deletion and a bounded 50-rule collection.
- Verify backup/restore, review locked dependency advisories and reuse synthetic browser sessions without weakening production login throttles.
- Document current limitations and owner hardware/phone/release gates. No external push or deployment.


## Startup plan and notification paging · 2026-10-07

- Add optional preview-first startup/install/removal scripts, validated native configuration and strict task ownership. No task is installed by development; native sign-in behavior awaits an explicit owner action.
- Keep the selected inbox page through refresh with latest-page navigation, bounded requests, cancellation and stale-response guards.
- Preserve generic alerts for unknown entities even alongside known non-matching objects, while retaining explicit suppression.
- Add timestamp-tie paging coverage and Windows task cmdlet doubles without modifying Task Scheduler or script execution policy.
