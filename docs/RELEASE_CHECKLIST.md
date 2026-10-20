# Local release and removal runbook

The owner explicitly authorized public visibility and the first development-preview release on 2026-10-20. Publish only the reviewed source and notices; runtime data, backup manifests, model files, private clips, session vaults and unredacted reports remain private.

The latest [release evidence review](RELEASE_AUDIT.md) distinguishes tested software from the remaining installation, phone, hardware and licence gates. Copied-source startup with existing dependencies is not a clean dependency installation.

## Before changing repository visibility

- [x] Owner selected MIT; root licence, package metadata and GitHub credit are included.
- [x] Clear source-install, optional AI, AI-disabled, hardware/module and phone guides are available.
- [x] Current lockfile advisory query completed: no known OSV matches across 155 pinned versions on 2026-10-20.
- [x] Resolve the missing uri-js-replace notice: retained authoritative MIT-0 grant, verified against unchanged upstream source and all eight installed dist files. Review additional platform/native/model notices before distributing those artifacts.
- [x] Remove the four historical machine-path references from published main/checkpoint history, preserve a private backup, align the checkout and verify a fresh clone. Git author metadata uses noreply; there are no PRs, forks or releases. GitHub cache/other-clone limits are recorded in the [privacy review](REPOSITORY_PRIVACY_REVIEW.md).
- [x] Run a local clean dependency installation from GitHub with a new venv, empty caches, isolated profile/tools and synthetic import/playback/restart. Completed on 2026-10-20 with 21 targeted checks after fixing one checkout-path assumption in a test.
- [x] On 2026-10-20, the owner reported completing a new-user Windows installation test, including script restrictions. The source install still requires a permitted script workflow; no signed packaged installer is provided. This is owner-reported acceptance, not a hosted-run result. Hosted checks remain blocked by GitHub account billing/spending limits.
- [x] On 2026-10-20, the owner reported completing a fresh archive backup/isolated restore with recordings, notes and settings, and a 24–48-hour reliability soak covering automatic recovery, sleep/resume and network interruptions. Exact duration, measurements and logs were not supplied to coding tools.
- [x] On 2026-10-20, the owner reported completing locked-screen/closed-app phone tests on Wi-Fi/cellular, thumbnails and tap-to-recording. These results cover the tested Android setup, not every browser or device. Session expiry/revocation and broader hardware checks remain separate where not explicitly reported.
- [x] Keep no-plan/module retrieval experimental until genuinely new eligible local clips pass the hardware gate. This preview makes no verified subscription-free retrieval claim.
- [x] Owner explicitly approved publication on 2026-10-20. Prepared the source-only `v0.1.0-dev.1` prerelease and reviewed [release notes](releases/v0.1.0-dev.1.md); publish that reviewed tag without personal artifacts.

## Reproducible software checks

1. Use a clean checkout outside OneDrive/SMB. Run `bootstrap.ps1 -Check` for the read-only runtime preflight, then review `bootstrap.ps1` before explicitly installing its locked dependencies. Record Python/Node/Edge and FFmpeg versions.
2. Run `test.ps1 -Browser`. Confirm native decoder checks ran, lint/types pass and the isolated desktop/tablet/phone/small-phone journeys pass. Do not call synthetic AI or push fixtures a real-device test.
3. Run the approved native generated-image/video smoke test. Review sampled owner observations locally; complete the labelled holdout in the acceptance specification.
4. Run `scripts/audit-dependencies.py` for the local preview; add `--online --include-push-candidates` for an explicit public-metadata advisory query. Inspect dependency notices, exact pins, model licences and intended distribution licence separately. The current [notice review](NOTICE_REVIEW.md) records four resolved notice gaps, including the verified uri-js-replace MIT-0 grant.
5. Stop the app, create a new backup, verify a restore to a new folder, then check expected counts, playable originals and annotations. Restored automation must remain paused; reconnect secrets separately.

## Owner-dependent acceptance

- Current cloud source: make a fresh harmless motion clip, confirm automatic discovery/download and recorded-time ordering across restart.
- New module: verify actual camera/module/storage and owner-confirmed no-plan entitlement. Retrieve three new distinct clips and a fourth after restart. Test unavailable/replaced storage and ambiguous IDs before claiming compatibility.
- Controls/live: explicitly approve any arm/disarm/motion write, verify observed state, then exercise bounded video, fullscreen, Record, Snapshot, stop/reconnect and Library playback.
- Phone: approve/configure HTTPS reachability, install optional push dependencies, complete native encryption checks and pair the actual browser. Check locked-screen display, Wi-Fi, cellular, expiry, revocation and authenticated tap-to-play separately.
- Run a 24–48-hour soak plus sleep/resume, network outage, token expiry, storage pressure and unavailable-volume recovery. Record measured delays, gaps and failures. Do not disable Windows sleep or install startup/service tasks implicitly.

Optional startup scripts are available for explicit review; no registration has been performed. Preview `install-startup.ps1` with the same data root/port/origin you want to use, then add `-Apply` only when approving that task. It uses the current PowerShell executable and current user interactive session, with no password, power change or policy bypass. The manual supported launch remains `start.ps1`; Node is not required to serve the built frontend. Do not run multiple workers/reload in production.

## Safe removal

Run `stop.ps1` and confirm graceful shutdown. Close the dev terminal. Before removing anything, use the printed resolved profile directory and make a verified backup of any recordings/notes you want to keep. Review the optional startup and remote-access components you enabled; installations differ. Remove only registrations, firewall rules, DNS entries or connectors owned by this Porchlight deployment, using the configuration you saved outside Git. If you later opt into startup, preview `uninstall-startup.ps1` with the original data-root override and add `-Apply` to remove only the checked registration. It does not stop a running app or delete data. Revoke paired browsers/permission and owner-managed remote access separately if configured. The source checkout and its `.venv`/`node_modules` may then be removed manually; deleting source does not delete the separately stored profile.

Removing the private profile deletes its archive and DPAPI vaults; this is irreversible and requires an explicit owner choice. Never delete the shared Ollama model store or unrelated FFmpeg installation. Any separately owner-configured Ollama setting belongs to its shared server; review it separately with other applications in mind.
