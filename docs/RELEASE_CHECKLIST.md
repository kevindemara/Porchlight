# Local release and removal runbook

Keep the repository private until publication checks and owner approval are complete. Development checkpoints have already been pushed privately. Do not publish runtime data, backup manifests, model files, private clips, session vaults or unredacted reports.

The latest [release evidence review](RELEASE_AUDIT.md) distinguishes tested software from the remaining installation, phone, hardware and licence gates. Copied-source startup with existing dependencies is not a clean dependency installation.

## Before changing repository visibility

- [x] Owner selected MIT; root licence, package metadata and GitHub credit are included.
- [x] Clear source-install, optional AI, AI-disabled, hardware/module and phone guides are available.
- [x] Current lockfile advisory query completed: no known OSV matches across 155 pinned versions on 2026-10-20.
- [ ] Resolve the missing uri-js-replace upstream notice; review other distribution notices for the intended artifact/platforms.
- [ ] Remove the historical machine paths or choose a clean-history publication plan; inspect Git author metadata and any GitHub attachments/artifacts. See [privacy review](REPOSITORY_PRIVACY_REVIEW.md).
- [ ] Run a clean dependency installation using the guide, plus the software checks below. Windows PR/manual checks are configured; the first manual runner was blocked by GitHub account billing/spending limits before any steps ran. A clean local test is an alternative; no paid service is required.
- [ ] Finish a fresh archive backup/restore and a 24–48-hour reliability soak, including automatic recovery, sleep/resume and network loss.
- [ ] Record phone locked-screen/closed-app Wi-Fi/cellular, preview and tap-to-recording results; retain clear browser/device limitations.
- [ ] Keep no-plan/module retrieval experimental until genuinely new eligible local clips pass the hardware gate. This need not block an honestly labelled paid-cloud development preview.
- [ ] Owner explicitly approves publication; create a reviewed release tag and change visibility only then.

## Reproducible software checks

1. Use a clean checkout outside OneDrive/SMB. Run `bootstrap.ps1 -Check` for the read-only runtime preflight, then review `bootstrap.ps1` before explicitly installing its locked dependencies. Record Python/Node/Edge and FFmpeg versions.
2. Run `test.ps1 -Browser`. Confirm native decoder checks ran, lint/types pass and the isolated desktop/tablet/phone/small-phone journeys pass. Do not call synthetic AI or push fixtures a real-device test.
3. Run the approved native generated-image/video smoke test. Review sampled owner observations locally; complete the labelled holdout in the acceptance specification.
4. Run `scripts/audit-dependencies.py` for the local preview; add `--online --include-push-candidates` for an explicit public-metadata advisory query. Inspect dependency notices, exact pins, model licences and intended distribution licence separately. The current [notice review](NOTICE_REVIEW.md) records three recovered notices and one unresolved upstream notice.
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
