# Porchlight

**A local-first Blink camera companion for Windows.** Save available recordings to your PC, browse and play them, and optionally add local AI descriptions, reviewed face matches and phone alerts.

Porchlight is free, open-source software under the [MIT licence](LICENSE), created by [Kevin DeMara](https://github.com/kevindemara). It is an independent project and is not affiliated with Amazon or Blink.

**Current status: Windows development preview.** Paid-cloud archiving and Android access have been tested. The project owner also reports completing a fresh backup/restore, a 24–48-hour reliability soak, locked-screen/closed-app phone checks and a new-user Windows installation test. These results cover the tested setup, not every camera, PC or browser. Subscription-free Sync Module retrieval remains experimental and unverified. See [known limitations](docs/KNOWN_LIMITATIONS.md) and [release evidence](docs/RELEASE_AUDIT.md).

**[Download Development Preview 1 — v0.1.0-dev.1](https://github.com/kevindemara/Porchlight/releases/tag/v0.1.0-dev.1)** for a fixed source snapshot and release notes. The default branch may contain newer development changes.

## How it works

Porchlight runs on **your Windows PC**. It checks Blink for available recordings, downloads them to a local archive and serves an interface you can open on the PC or, with optional HTTPS setup, on your phone. Your phone is a viewer and remote control for that PC; it does not run the recording or AI services.

1. **Save:** Porchlight checks for new cloud clips every 60 seconds by default. Available clips are saved locally and appear in Activity. Temporary failures retry automatically; an expired Blink login needs you to sign in again.
2. **Describe, optionally:** local Ollama analysis can add descriptions, and opt-in face matching can suggest names you have reviewed. Saving a recording does not wait for AI to succeed.
3. **Notify, optionally:** enabled rules can send phone alerts. A generic alert can arrive first, followed by a quiet update with a description, reviewed name or thumbnail when available. Polling, Blink availability, processing and phone connectivity all affect timing.

Recordings, saved analyses and credentials are stored on your PC. New Blink retrieval still uses Blink's internet services. Optional Web Push uses browser-vendor delivery services, and a tunnel provider can carry remote viewing traffic if you choose that route. Private footage is never sent to a cloud AI service by Porchlight.

**Keep the PC awake and Porchlight running** for new imports, analysis, remote viewing and alerts. Already archived recordings remain available on the PC during a Blink outage. Installing the phone app does not move your archive to the phone or provide offline playback.

## What you can do

- Automatically archive available Blink cloud clips, with durable discovery checkpoints, deduplication and automatic recovery from temporary errors.
- Browse recordings, saved live recordings and snapshots together in Activity; search, favourite, annotate, export and play protected local files.
- Start supported live views, listen when the camera supplies usable audio, save a live recording or snapshot, and manage supported camera controls. Live sessions are bounded and use camera battery; two-way talk and continuous recording are not supported.
- Add optional Ollama descriptions and opt-in SFace face-match suggestions for names you review. AI can stay disabled; recording collection and playback do not depend on it.
- Install the web app on an Android home screen and pair optional Web Push alerts, including descriptions and protected previews where supported.
- Review storage retention, diagnostics, backups and restore validation.

## Install and run

This is a **Windows source installation**, not a packaged installer. You do not need Codex, Docker, a hosted database or an AI API key. The PowerShell scripts require an existing policy that permits reviewed local scripts; check the [PowerShell prerequisite](docs/QUICK_START.md#check-the-powershell-prerequisite) before starting. No policy bypass is included.

You need a Blink account and an available recording source for automatic camera collection, internet access for setup and Blink retrieval, and local disk space for the archive. AI additionally needs a suitable local Ollama model and enough memory to run it; it is optional. Start without AI if you are unsure.

1. Install [Python 3.12–3.14](https://www.python.org/downloads/windows/) and a supported [Node.js release, 22.12 or newer](https://nodejs.org/en/download). Enable Python PATH in its installer, then open a new PowerShell terminal.
2. On [GitHub](https://github.com/kevindemara/Porchlight), choose **Code → Download ZIP**, extract it to a local folder outside OneDrive, and open that folder in PowerShell. Use the folder containing `setup.ps1`, not the ZIP itself. Alternatively, with Git installed:

   ```powershell
   git clone https://github.com/kevindemara/Porchlight.git
   Set-Location Porchlight
   ```

3. Check requirements, then run the interactive setup:

   ```powershell
   .\setup.ps1 -Check
   .\setup.ps1
   ```

   Type `YES` to install the locked application packages. Unless you have already configured FFmpeg and ffprobe, also accept the separate **FFmpeg media-tools** offer: these tools are needed for recording processing, thumbnails and live view. Setup installs them in your Windows user folder without changing global PATH. It does not install AI models, publish the app or change your router.

4. Start the app:

   ```powershell
   .\start.ps1
   ```

5. Leave the terminal running and open **http://127.0.0.1:8765** on this PC. Create your local owner account with a strong, unique passphrase; it is separate from your Blink login. Follow the setup guide to connect Blink and complete verification, select your hardware and explicitly enable the recording source. Choose **Use Porchlight without AI** to skip AI. Confirm a genuinely new clip appears in Activity and plays.

For prerequisites, ZIP extraction, camera/module selection, optional AI, push notifications, updates, backups and troubleshooting, follow the **[step-by-step Windows installation guide](docs/QUICK_START.md)**.

To stop this instance, open a second PowerShell terminal in the same source folder and run `.\stop.ps1`. The shared Ollama service and unrelated projects are left running. Run `.\start.ps1` again after restarting Windows; normal setup does not register automatic startup or create desktop launchers. The default archive and encrypted credentials live under `%LOCALAPPDATA%\Porchlight`, outside the source folder. Keep that data on a local disk, outside OneDrive or network shares, and [back it up](docs/ARCHIVE_AND_BACKUP.md). Follow [Update safely](docs/QUICK_START.md#update-safely) before installing a newer version.

## Blink storage and subscriptions

Porchlight itself is free and does not require a paid AI service or a Porchlight account subscription. **That does not guarantee your Blink cameras can supply recordings without a Blink plan.** Automatic collection requires a recording source your actual camera, module and account can provide. Paid-cloud imports are tested; subscription-free retrieval is not yet verified.

The setup guide includes choices for Core, original Sync Module, Sync Module 2, XR, XR+, no-module and mixed setups. Selecting a model guides setup; it does not certify compatibility. Sync Module 2 USB storage and XR/XR+ microSD retrieval remain experimental and are offered only when observed device status permits a test. Daily card backups made during a plan differ from direct local recordings; card usage alone does not mean Porchlight can retrieve those files.

Read the [compatibility and no-plan validation guide](docs/02_BLINK_COMPATIBILITY_AND_NO_SUBSCRIPTION.md). Do not cancel a plan based on this preview. Unofficial Blink access depends on Blink's internet services; Porchlight is not an offline Blink replacement or a continuous recorder. Manual imports remain available.

## Optional AI

All inference runs through your local Ollama installation. No cloud AI fallback is used. The wizard checks local capabilities, explains model installation, offers a synthetic test and lets you skip AI entirely. Hardware estimates are guidance, not a performance guarantee. Models are downloaded only through your explicit local actions and are not bundled.

Without AI, you still get available recordings, camera/time/source information, thumbnails, playback, favourites, notes and optional generic alerts. Blink's own smart descriptions are not guaranteed to be available through the unofficial integration.

Face recognition is opt-in and limited to names you review. Possible matches and descriptions can be wrong; review the original recording. See [local AI setup](docs/LOCAL_AI_SETUP.md) and [face recognition](docs/FACE_DETECTION.md).

## Phone access and notifications

The responsive website can be installed from Android Chrome's menu once it has a reachable, trusted HTTPS address. This adds an app-like home-screen icon; there is no APK to install. **The PC address `127.0.0.1` will not connect your phone to your PC**—on the phone it means the phone itself.

Start with [phone setup](docs/PHONE_SETUP.md). [Direct home HTTPS](docs/DIRECT_HTTPS.md) can work without a phone VPN when your ISP/router permits inbound access. [Cloudflare private access](docs/CLOUDFLARE_BACKUP.md) is an optional backup requiring an enrolled phone client; it is not required by Porchlight. These are explicit owner-managed choices, not automatic network changes.

After choosing a route, open the exact HTTPS address in phone Chrome, sign in and verify playback on cellular as well as home Wi-Fi. Then choose Chrome's **Install app / Add to home screen**. Remote access needs a running HTTPS proxy and, for a tunnel route, its connector too. The phone guide explains the separate setup; `start.ps1` starts Porchlight, not third-party proxies or connectors. Android Chrome is the tested phone path; other browsers and iOS are not yet verified.

For alerts, follow [Web Push setup](docs/WEB_PUSH.md): install the optional push packages on the PC, restart Porchlight, create local push keys, then allow notifications and pair the phone in **Settings → Notifications**. Send a test alert and enable a notification rule with **Also send to paired browsers**. Descriptions and thumbnails are separate opt-in rule settings; installing the home-screen icon alone does not enable alerts.

Tapping an activity alert opens that recording; a test alert opens the inbox. Thumbnails and playback require a reachable PC and a valid signed-in phone session. Android controls notification layout and lock-screen visibility, so expand an alert to check its image. Text-only alerts remain possible when a private preview cannot load. Alert arrival time is not guaranteed.

## If something is missing

| Problem | Where to start |
|---|---|
| No new recordings | Settings → Cameras & recording: confirm the source is enabled and check its status. Temporary errors retry with backoff; authentication errors need a fresh sign-in. Expired Blink clips cannot be recovered. |
| “Configure FFmpeg” | Accept the media-tools offer in setup, then stop/start Porchlight. Both FFmpeg and ffprobe must be detected. |
| AI is unavailable or slow | Keep AI disabled and use the archive normally; follow the local AI guide before changing models. |
| Phone cannot connect | Verify the PC, app and HTTPS proxy are running. Open the exact HTTPS address in Chrome before testing the installed app. |
| Push test works, camera alerts do not | Check the enabled rule, paired-browser delivery and any filters or quiet hours. A push test does not prove a recording matches a rule. |

More troubleshooting and update instructions are in the [Windows guide](docs/QUICK_START.md#common-problems).

## Security, development and release

Credentials belong in the local setup forms, never in Git or issue reports. Media routes require authentication; inference stays on loopback. Do not expose Ollama or the backend port directly. Runtime data, private network configuration, certificates and keys belong outside the checkout.

- [Development and test commands](docs/LOCAL_DEVELOPMENT.md)
- [Architecture](docs/03_ARCHITECTURE.md), [milestone plan](docs/12_IMPLEMENTATION_PLAN.md), [build status](BUILD_STATUS.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md), [privacy audit](docs/REPOSITORY_PRIVACY_REVIEW.md), [third-party notices](THIRD_PARTY_NOTICES.md)
- [Original product requirements and specification index](docs/00_PRODUCT_REQUIREMENTS.md); the numbered documents preserve the target design, while build status records implemented evidence.

To reproduce software checks in an installed development checkout:

```powershell
.\test.ps1 -Browser
```

Tests use isolated profiles and synthetic fixtures. They do not establish hardware compatibility, visual accuracy or actual phone delivery. When reporting a problem, include versions and redacted error codes; exclude recordings, face templates, account IDs, cookies, tokens and backup files.

## Licence and credits

Porchlight's original code and documentation are [MIT licensed](LICENSE), allowing reuse and modification under its terms, including commercial use. Dependencies retain their own licences; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). FFmpeg executables and AI model weights are not bundled.

Created by **[Kevin DeMara](https://github.com/kevindemara)**. GitHub credit also appears in the app footer.
