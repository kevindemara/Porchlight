# Porchlight

**A local-first Blink camera companion for Windows.** Save available recordings to your PC, browse and play them, and optionally add local AI descriptions, reviewed face matches and phone alerts.

Porchlight is free, open-source software under the [MIT licence](LICENSE), created by [Kevin DeMara](https://github.com/kevindemara). It is an independent project and is not affiliated with Amazon or Blink.

**Current status: development preview.** The application runs locally and has real paid-cloud and Android integration evidence. Fresh no-subscription retrieval, a clean-machine installation and the full reliability soak remain unverified. See [known limitations](docs/KNOWN_LIMITATIONS.md) and [release evidence](docs/RELEASE_AUDIT.md).

## What you can do

- Automatically archive available Blink cloud clips, with durable discovery checkpoints, deduplication and automatic recovery from temporary errors.
- Browse recordings, saved live recordings and snapshots together in Activity; search, favourite, annotate, export and play protected local files.
- Use capability-gated live viewing, optional supplied audio, Record, Snapshot and observed-state camera controls.
- Run optional Ollama vision descriptions and opt-in, locally reviewed SFace name suggestions. AI can stay disabled; recording collection and playback do not depend on it.
- Install the web app on an Android home screen and pair optional Web Push alerts, including descriptions and protected previews where supported.
- Review storage retention, diagnostics, backups and restore validation.

## Install and run

This is a **Windows source installation**, not a packaged installer. You do not need Codex, Docker, a hosted database or an AI API key.

1. Install [Python 3.12–3.14](https://www.python.org/downloads/windows/) and a supported [Node.js release, 22.12 or newer](https://nodejs.org/en/download). Enable Python PATH in its installer, then open a new PowerShell terminal.
2. Download and extract this repository to a local folder outside OneDrive, or clone it:

   ```powershell
   git clone https://github.com/kevindemara/Porchlight.git
   Set-Location Porchlight
   ```

3. Check requirements, then run the interactive setup:

   ```powershell
   .\setup.ps1 -Check
   .\setup.ps1
   ```

   Setup asks before installing locked dependencies and separately offers the pinned FFmpeg media tools. Review each prompt. It does not install AI models, expose a server or change your router.

4. Start the app:

   ```powershell
   .\start.ps1
   ```

5. Leave the terminal running and open **http://127.0.0.1:8765**. Create your local owner account, connect Blink through the local form and follow the setup guide. Choose **Use Porchlight without AI** to skip AI. Enable the appropriate recording source and verify a new clip appears and plays.

For prerequisites, ZIP extraction, camera/module selection, optional AI, push notifications, updates, backups and troubleshooting, follow the **[step-by-step Windows installation guide](docs/QUICK_START.md)**.

To stop this instance, open a second PowerShell terminal in the checkout and run `.\stop.ps1`. The shared Ollama service and unrelated projects are left running. The default archive and encrypted credentials live under `%LOCALAPPDATA%\Porchlight`, outside the source checkout. Keep that data on a local disk, outside OneDrive/SMB, and [back it up](docs/ARCHIVE_AND_BACKUP.md).

## Blink storage and subscriptions

Porchlight does not require you to purchase a Blink subscription. **Automatic collection still requires a recording source that your actual camera, module and account can provide.** Successful paid-cloud imports do not establish subscription-free compatibility.

The wizard supports Core, original Sync Module, Sync Module 2, XR, XR+, no-module and mixed setups. Sync Module 2 USB storage and XR/XR+ microSD retrieval are capability-gated experimental paths. Plan-covered daily card backups differ from direct local recordings. A selected hardware type does not grant a capability, and an empty local feed does not prove retrieval works.

Read the [compatibility and no-plan validation guide](docs/02_BLINK_COMPATIBILITY_AND_NO_SUBSCRIPTION.md). Do not cancel a plan based on this preview. Unofficial Blink access depends on Blink's internet services; Porchlight is not an offline Blink replacement or a continuous recorder. Manual imports remain available.

## Optional AI

All inference runs through your local Ollama installation. No cloud AI fallback is used. The wizard checks local capabilities, explains model installation, offers a synthetic test and lets you skip AI entirely. Hardware estimates are guidance, not a performance guarantee. Models are downloaded only through your explicit local actions and are not bundled.

Face recognition is opt-in and limited to names you review. Possible matches and descriptions can be wrong; review the original recording. See [local AI setup](docs/LOCAL_AI_SETUP.md) and [face recognition](docs/FACE_DETECTION.md).

## Phone access and notifications

The responsive website can be installed from Android Chrome's menu once it has a reachable, trusted HTTPS address. **Installing the home-screen app does not host Porchlight:** the PC must remain awake and connected.

Start with [phone setup](docs/PHONE_SETUP.md). [Direct home HTTPS](docs/DIRECT_HTTPS.md) can work without a phone VPN when your ISP/router permits inbound access. [Cloudflare private access](docs/CLOUDFLARE_BACKUP.md) is an optional backup requiring an enrolled phone client; it is not required by Porchlight. These are explicit owner-managed choices, not automatic network changes.

[Web Push setup](docs/WEB_PUSH.md) explains optional dependency installation, browser permission and pairing. Browser-vendor push services carry encrypted messages. Thumbnails/video still need authenticated access to your PC, and Android presentation varies. Test closed/locked-screen delivery on Wi-Fi and cellular and tap-to-recording separately.

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

Porchlight's original code and documentation are [MIT licensed](LICENSE). Dependencies retain their own licences; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). FFmpeg executables and AI model weights are not bundled. A missing upstream development-dependency notice and the remaining acceptance checks are recorded in the release checklist.

Created by **[Kevin DeMara](https://github.com/kevindemara)**. GitHub credit also appears in the app footer.
