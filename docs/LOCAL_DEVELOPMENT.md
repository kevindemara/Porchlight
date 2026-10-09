# Running the local development build

This is a Windows development build, not the completed release. On 2026-10-08, the owner approved the first development snapshot in the private [kevindemara/Porchlight repository](https://github.com/kevindemara/Porchlight). Clone that repository with an authorized GitHub account, then follow the setup below. The application and private runtime data still run locally; a source push does not deploy the application or install a Windows service. Hardware, phone and release acceptance remain incomplete.

Use PowerShell in the project directory outside OneDrive. Verified prerequisites on this PC: Python 3.12.10, Node 24.19.0 and npm 11.17.0. The backend requires Python >=3.12,<3.15; this development lock was tested on Windows with Python 3.12. Browser checks use an installed Microsoft Edge.

```powershell
Set-Location C:\Projects\Porchlight
.\bootstrap.ps1 -Check  # Read-only runtime preflight; installs nothing.
.\bootstrap.ps1         # Explicitly install the locked dependencies and build.
.\start.ps1
```

Open <http://127.0.0.1:8765>. Create the single local owner account with a password of at least 12 characters. There is no default password. Then open Settings to connect Blink using its email, password and verification code in that local screen. Do not paste those credentials or private clips into a coding conversation. Blink password/code are transient; reusable session material uses the current Windows user's DPAPI encryption. Inventory reads do not establish recording access.

The application uses `%LOCALAPPDATA%\Porchlight` for SQLite, media, import journals and encrypted sessions. It binds only to `127.0.0.1`; it does not create firewall rules or remote access. Use the exact URL above. Built frontend assets are served by Python; Node is needed to build/develop, not to serve the built application.

After connecting Blink, open Settings → Cameras & recording → Save camera recordings → **Sync recordings**. This enables cloud-to-PC archiving, beginning with a seven-day discovery window and subsequent checks about every 120–130 seconds. Each new routine cloud scan rechecks at least the previous 24 hours so clips surfaced behind the incremental checkpoint can still be found. Stable source keys prevent repeated listings from duplicating recordings or download jobs. Older history uses the separate historical controls. Pagination and jobs are durable; work is bounded to 20 pages per lease and resumes incomplete scans using their original cutoff/page. Downloads are serialized, limited to four attempts before explicit retry, and respect provider Retry-After. Pause sync to stop new work; an in-progress transfer can finish. Discovered/pending/failed counts remain visible even when a clip is not playable; only validated archived clips enter Activity. The first Activity page refreshes about every ten seconds.

Original clips stay in Blink. This does not enable local recording on a Sync Module Core. The owner's packaging identifies Core, which has power-only USB-C and no supported local storage or clip backup. The paid plan can supply cloud clips for PC archiving. USB/microSD module recording and no-plan compatibility are separate, unverified paths. Set the plan/trial state under Workspace; that records owner confirmation rather than inferring entitlement from a successful download.

Cameras refreshes archive evidence every ten seconds. A camera with archived cloud clips shows **Recording access verified** and **Cloud clips saved locally**. Its preview comes from the newest saved clip by recorded time, falling back to discovery time when unknown; old clips imported later do not replace newer dated clips. The caption identifies it as a saved clip and shows its recorded time. Click the preview to play that recording. JPEG previews are generated locally with FFmpeg, cached under the private profile's `thumbnails/` directory, and served only after local authentication with browser caching disabled. No Blink snapshot command or AI request is involved. A missing or undecodable preview leaves the recording button usable. No-plan retrieval remains a separate verification gate.

Microsoft Store app isolation may resolve that data folder into an application package cache. The startup terminal prints the actual resolved directory, and stop/development scripts query the same Python configuration. On this Codex host it resolves under `%LOCALAPPDATA%\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\Porchlight`. Set an explicit `PORCHLIGHT_DATA_ROOT` on a normal local disk if you prefer a location independent of the desktop app's package.

To stop the process, use Ctrl+C in its terminal or run `./stop.ps1` in a second PowerShell. Shutdown is cooperative and does not forcibly kill an arbitrary PID. Only one process per data profile is supported.

## FFmpeg

FFmpeg 9.0.2 and ffprobe are installed for this PC in `%LOCALAPPDATA%\Porchlight\tools\ffmpeg\bin`. Porchlight finds them directly; a global PATH change is unnecessary. On another PC, installing them is an explicit step:

```powershell
.\scripts\install-ffmpeg.ps1
```

The script verifies the pinned archive's SHA-256 before extraction. It retains the archive, package licence/docs, build configuration and installation record outside the repository. The selected Gyan essentials build is GPL-3.0-or-later; binaries are not bundled. For an existing custom install, set `PORCHLIGHT_FFMPEG` and `PORCHLIGHT_FFPROBE` to absolute executable paths before starting the app.

MP4 uploads are bounded to 256 MiB, five minutes and 4096 pixels per edge. JPEG imports are bounded to 32 MiB and a validated single image, with unknown recording time unless supplied. The default free-space reserve is five GiB and is configurable under Local archive. FFprobe checks metadata and FFmpeg decodes the video before promotion. Recording timestamps remain unknown unless explicitly supplied. Reimporting the same bytes with the same recording time preserves the event and repairs its original file. Automatic cleanup starts off and requires a reviewed preview before enabling it.

## Ollama

The existing native service is used at <http://127.0.0.1:11434>. No model is bundled or downloaded automatically. `qwen3.8-27b-local:latest` passed a synthetic two-colour image test on this PC; GPT-OSS models reported no vision support. A cold first call took 54.77 seconds, so this is an initial working candidate, not a measured camera-analysis latency claim.

`C:\local-models` contains local model configuration; Ollama's existing shared model store is left in place. The app rejects remote/cloud aliases using runtime metadata and checks `/api/status` before sending private images. The owner approved disabling Ollama cloud features on this PC and restarted it; the running server now confirms `cloud.disabled=true`.

On another PC, review the explicit local-only configuration step first:

```powershell
.\scripts\configure-ollama-local.ps1          # Preview only
.\scripts\configure-ollama-local.ps1 -Apply   # Explicit opt-in
```

This saves `disable_ollama_cloud=true` in the Windows user's `.ollama\server.json`, preserving other settings and backing up an existing configuration. Quit Ollama from its system-tray menu and reopen it afterward. This shared setting disables Ollama cloud models and web search for every application using that server. Local models remain installed. Porchlight itself does not change this setting or restart Ollama. [Ollama's documented local-only setting](https://docs.ollama.com/faq).

To try descriptions, reload Porchlight, open Settings → AI → Local AI → **Check local models**, select an installed vision model and run its **synthetic image test**. Select the tested model and **Save settings**. Open an existing clip in Activity and select **Analyze recording** for a controlled first test without enabling automatic analysis. Enable **Analyze new recordings automatically** separately if desired. Older recordings are processed on request; automatic analysis only considers camera clips discovered after enabling AI and recorded within the last 24 hours. Turning the checkbox off pauses automatic work. Explicit Analyze recording requests still run with a selected, tested local model; recording sync and playback continue.

Once enabled, completed cloud/local downloads signal analysis immediately after durable archiving. A separate scheduler can queue new arrivals while the single inference worker is busy; it does not delay downloads. The bounded durable queue processes one clip at a time, with a 30-second recovery scan for missed signals/restarts. Local-only/model verification and retries can delay analysis, and failed analysis leaves the original recording playable. The owner profile now has this enabled using the existing tested Qwen model and Balanced preset; new installations still default to off.

The worker samples up to six chronological frames, drops near-duplicates, validates the model's structured output and builds a neutral description from permitted fields. Descriptions become searchable. Still/repeated images cannot establish movement; uncertain or monochrome evidence suppresses colour claims. Analysis revisions retain model/contract digests, frame hashes/timestamps and uncertainty, with frames kept in memory rather than derivative files. Failed analysis leaves the original recording playable. These safeguards do not establish visual accuracy; review descriptions against clips locally. Optional, separately installed SFace recognition is described in [FACE_DETECTION.md](FACE_DETECTION.md).

An optional native integration check processes generated pixels in a temporary, isolated profile without connecting Blink:

```powershell
.\.venv\Scripts\python.exe scripts\smoke-local-ai.py --model qwen3.8-27b-local:latest
```

It exercises the installed model, FFmpeg, durable queue and validated description contract. It does not measure real camera accuracy or change the owner's AI settings.

## One-clip AI test

For an explicit one-clip AI test, stop the regular application and run `.\.venv\Scripts\python.exe scripts\probe-latest-ai.py --model <installed-local-vision-model>`, then restart it. The CLI selects the newest saved cloud clip associated with current inventory, verifies running local-only Ollama/model-test gates, and requests one analysis. It uses an in-memory one-clip opt-in; persisted automatic-AI settings are unchanged. It reports only validated fields or safe failure codes, never imagery or raw model prose. It does not leave a silent retry behind. CLI tests require the same private-profile lock as the app.

## Experimental live view

Live view includes **Record**, **Stop recording** and **Snapshot** while fresh video is playing. Record saves complete video segments locally until you stop recording or end/leave the live session. Snapshot saves the displayed frame as a JPEG. Open **Activity** and use **All / Recordings / Snapshots** to find these captures alongside camera/cloud clips and manual imports, with distinct source labels. Expand a capture to play/view/download it. Capturing is explicit and does not enable AI or modify Blink subscriptions. Files stay in the private profile under `media/live-library/`; see [LIVE_VIEW.md](LIVE_VIEW.md) for limits and interruption recovery. Real-camera capture/save remains an owner validation step.

Open **Live view** from the navigation, choose a camera and select **Start live view** for a video-only session of up to 90 seconds. Switching cameras or leaving the page stops the stream; opening the page does not start one. Compatibility remains experimental; no audio or continuous capture is implemented. The actual camera relay uses a self-signed certificate, so Porchlight requires explicit review of its exact fingerprint before trusting it. Approval is scoped to Porchlight and can be revoked from Settings → Diagnostics → Readiness → **Reset live relay trust**. See [LIVE_VIEW.md](LIVE_VIEW.md) for the transport, tests and short hardware probe. No certificate is trusted automatically.

## Development and verification

```powershell
.\dev.ps1                 # Vite at http://127.0.0.1:5174; backend at :8765
.\test.ps1                # Python tests, lint/types, TypeScript and production build
.\test.ps1 -Browser       # Also run Edge browser journeys at four viewport sizes
```

Stop the ordinary server before using `dev.ps1`. Backend changes require restarting it. Browser tests use separate temporary profiles and ports 18765–18768 for four viewport sizes. They generate synthetic MP4s, use synthetic owner credentials and do not log in to Blink. Browser AI responses are explicitly labelled fixtures; backend integration tests exercise the actual queue/FFmpeg with a model HTTP fixture. Run the optional native check above for actual Ollama evidence. Run the FFmpeg installer first to exercise decoder checks rather than skip them.

Configuration overrides use environment variables: `PORCHLIGHT_DATA_ROOT` (local path outside the repo), `PORCHLIGHT_PORT`, `PORCHLIGHT_TIMEZONE`, `PORCHLIGHT_OLLAMA_URL`, `PORCHLIGHT_FFMPEG`, `PORCHLIGHT_FFPROBE`. No credentials belong in environment files or source control.

Runtime upgrades run Alembic migrations at startup under an exclusive profile lock. Cloud discovery/download, independent analysis, archive filters/corrections/deletion, search interpretation/digests, transactional local inbox rules, backup/restore and optional previewed retention are implemented. See [ARCHIVE_AND_BACKUP.md](ARCHIVE_AND_BACKUP.md). Sync Module local retrieval has a separate experimental worker and requires active eligible storage reported by the API; actual hardware and phone delivery remain unverified. Do not treat this build as the sole archive of important recordings. Exact dependencies are in `requirements.lock` and `apps/web/package-lock.json`; licence intake is recorded in [DEPENDENCY_INVENTORY.md](DEPENDENCY_INVENTORY.md).

Current media compatibility limit: only validated relative paths on the authenticated Blink REST host are accepted. Signed/external locators and redirects fail with a safe compatibility reason rather than forwarding credentials to an unverified host. Recordings with missing/ambiguous timestamps remain unknown; ambiguous camera identifiers are not guessed from names.

## Sync Module recording candidate

Settings → Sync Module local storage is separate from cloud sync. It shows observed module eligibility, archived/pending counts and explicit start/pause controls. Enabling it requests manifests through Blink, then prepares and downloads listed clips into the PC archive. There is no direct LAN mount, removable-card formatting or subscription change. Core stays unavailable. Active compatible storage is a candidate capability; a successful local transfer and a no-plan claim require separate real tests. No local scan is enabled by default. Pause affects new work; an already-started transfer can finish.

The upstream manifest does not provide a verified storage-volume generation identifier. Replaced/reformatted cards and upstream clip-ID reuse need real hardware validation. See [adapter details](BLINKPY_API_MAP.md) and [limitations](KNOWN_LIMITATIONS.md).

## Rules, controls and diagnostics

Notifications provides a local inbox, test, snooze and up to 50 rules with enable/pause, edit and confirmed delete. Schedules use an explicit IANA timezone, weekdays, quiet hours and cooldown. Deleting a rule keeps saved recordings and existing inbox messages. Optional phone pairing is described in [WEB_PUSH.md](WEB_PUSH.md); no push permission is requested merely by opening the page.

Cameras → Camera controls shows observed network arm and camera motion states when supported. Disabling either requires confirmation. Network arm affects all cameras on that network. Pending commands are not shown as success until refreshed remote state matches. Unknown outcomes support a read-only verification; interrupted commands are never automatically resent. These model-specific methods have synthetic tests; owner hardware changes have not been exercised unattended.

Settings → Diagnostics → Readiness → Download redacted diagnostics exports an allowlisted JSON report with versions, safe counts, configured storage limits and missing-file totals. It excludes account tokens, footage, names, event descriptions, IDs and filesystem paths. Local AI also reports shared Ollama loaded-model count and GPU allocation from `/api/ps`, with a possible-contention notice. This read-only check neither unloads models nor measures other GPU applications. [Ollama running-model API](https://docs.ollama.com/api/ps).

No startup task/service is installed. The built app can be launched with `start.ps1` in your own Windows session. Optional startup scripts are preview-first:

```powershell
.\install-startup.ps1                    # Preview, no Task Scheduler access
# Add -DataRoot 'C:\PorchlightData' and -Port/-PublicOrigin if used for your profile.
.\install-startup.ps1 -Apply             # Explicit owner opt-in; next sign-in, not now
.\uninstall-startup.ps1                  # Preview only
.\uninstall-startup.ps1 -Apply           # Remove only the checked registration; keep data
```

Use the same data root during removal. The task is tied to this checkout/profile/current Windows user and refuses unrelated tasks or silent configuration replacement. It uses interactive limited privileges, the current PowerShell executable, single-instance scheduling and at most three failure restarts, without waking the PC, storing a password or changing execution policy. The native app provides readiness and its profile lock; Ollama is neither started nor changed. If script policy blocks execution, use your established reviewed policy workflow; do not bypass it automatically. Keep the checkout, virtual environment, built assets, shell executable and media paths available. Actual Task Scheduler registration and sign-in behavior still need owner testing. See [release and safe removal checks](RELEASE_CHECKLIST.md).

Inbox pages now remain on the selected older cursor during periodic refresh. Choose Latest notifications to return to the current page. If the cursor's anchor was deleted, the app reports the problem and returns to latest. An unknown entity alongside unrelated known objects retains a generic alert under the default unknown policy.

## Historical recordings, evidence and status updates

Settings → Cameras & recording → Save camera recordings → Retrieve older cloud recordings offers 7/30/90/365 days or all still available. Start, Stop history retrieval and Resume history operate independently of ordinary sync. Cursors and an operation generation survive restart; cancelled in-flight discovery cannot advance the replacement cursor. History preserves source keys/content deduplication and honours Retry-After. Historical clips are labelled in Activity and details; they never alert or auto-analyze. Analyze one explicitly when needed. History has not been activated against the owner's account during unattended development.

Settings → AI → Local AI → AI workload offers Balanced (up to 6 frames, 960 px, 8192 context) and Light (up to 3 frames, 640 px, 4096 context). Save applies to new requests; queued requests retain their preset. Both use the same local-only gates and 8 MiB image budget. The native Light experiment failed validation; it is an option to evaluate, not a recommended accuracy improvement. CLI probes accept `--workload balanced` or `--workload light` without changing saved automatic settings.

Analysis details now show sampled images for the current extraction version. Selecting a video sample seeks the original player. The owner-authenticated endpoint recreates the exact JPEG and verifies its saved hash; unavailable samples can be retried. No evidence copies accumulate on disk. Original recordings remain usable after AI/preview failure.

Cameras can group by network or local group. Activity groups its existing newest-first ordering by the configured local date and displays validated object categories, historical provenance and current retrieval warnings. Coverage warnings describe known interruptions rather than imply continuous Blink monitoring.

One authenticated SSE connection sends bounded topic-only invalidations. Session revocation closes the signed-in workspace; restart, invalid/replayed cursors or a 512-row gap cause resync. Existing guarded polling remains a fallback. Readiness reports inventory/list/download/AI/disk/push and actual worker-loop checks independently. Last success labels use observed operations, and provider acceptance does not establish phone receipt.

`dev.ps1` waits for its unique launch ID and native health before starting Vite on 5174. This avoids treating the Windows virtual-environment launcher's PID as the actual server PID. Cooperative shutdown also closes connected SSE clients. Mapped network drives are rejected as runtime storage, as are UNC/OneDrive/source-tree locations.


## Guided setup

After creating your local owner, open the small **Open setup guide** action in Settings (labeled **Review setup** when cameras are connected). Settings has Cameras & recording, AI, Storage, Notifications, Appearance and Diagnostics sections. Manage camera names, grouping and controls through **Live View → Manage cameras**; the Network · Armed/Disarmed/Unknown button beside Manage cameras opens arm/disarm controls in a modal. The notification bell opens the inbox; its **Notification settings** shortcut leads to push pairing and rule editing. The guide separates privacy/storage/Blink/source/model/phone/readiness; each step reuses the same protected settings and forms. Independent work can continue when Blink is not signed in. Continue/Skip merely navigate: they do not enable recording sync, AI, retention, live view or notifications. Skipped states remain observed/unverified. Model tests, source starts, budget saves and phone pairing still require their explicit controls. The final review distinguishes saved cloud access from verified no-plan retrieval.

The current folder is shown with disk reserve/budget controls. To choose another folder, stop the app and set PORCHLIGHT_DATA_ROOT before launch, or use stopped backup/new-profile restore. The guide never moves a live SQLite database. Steps can be revisited; returning to Settings refreshes its draft so saved guide changes do not leave a stale revision. Step/close focus and four viewport journeys are tested. New hardware and real phone acceptance still require the separate release checks.


## Large archives and label review

Activity retains loaded older pages when saving notes, reviewing AI or deleting a recording. Long histories render measured visible rows with keyboard access and preserve scroll/focus. Object filters use your corrected labels where supplied, otherwise the latest accepted AI revision. Open recording details → **Description is wrong · correct object labels** to edit category/type/colour/actions/direction. Save stores the whole object set; removing every object explicitly saves an empty set. Use original AI labels clears the override. The editor's conflict reload protects against another view's label changes. Corrections persist through reanalysis and backup/restore and send no new alert. Original AI evidence remains separately labelled.

The latest native Light diagnostic rejected an inconsistent subtype after45.77 s. Balanced remains selected. This is validation behavior, not a visual accuracy benchmark; compare accepted descriptions against footage locally.
