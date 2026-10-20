# Set up Porchlight on Windows

Start with a working camera archive. AI and phone access are optional additions; neither is required to save and watch available clips. This is a source installation, not yet a packaged one-click installer.

## 1. Prepare the PC

Use a local folder outside OneDrive, such as `C:\Apps\Porchlight`. Download/extract the repository there. Keep the PC’s normal Windows user account for setup and running the app; its encrypted credentials belong to that user.

On [GitHub](https://github.com/kevindemara/Porchlight), choose **Code → Download ZIP**, extract the ZIP, and open the extracted folder containing `setup.ps1`. Do not run scripts from inside the ZIP. For the fixed first preview, use the source ZIP from the [v0.1.0-dev.1 release](https://github.com/kevindemara/Porchlight/releases/tag/v0.1.0-dev.1).

Alternatively, if Git is installed, open PowerShell in your chosen parent folder:

```powershell
git clone https://github.com/kevindemara/Porchlight.git
Set-Location Porchlight
```

Git is optional for a ZIP installation. Do not enter GitHub or Blink passwords in a script or this repository.

Install these prerequisites if missing:

- [Python for Windows](https://www.python.org/downloads/windows/), version **3.12 through 3.14**. Tick **Add Python to PATH** in its installer. The development build was tested with 3.12.10.
- [Node.js with npm](https://nodejs.org/en/download), a supported release satisfying **22.12 or newer**. The development build was tested with 24.19.0. Node builds the interface; it is not the production web server.

Ollama, Docker, a cloud database, a paid AI API and a Cloudflare account are **not** prerequisites. Recording access depends on the Blink hardware/storage/account; do not cancel a plan based on successful paid-cloud imports.

### Check the PowerShell prerequisite

This source installer also needs a PowerShell environment whose existing policy permits reviewed local scripts. The local clean-install test used PowerShell 7; the same PC's Windows PowerShell blocked scripts before setup could run. Python and Node alone do not resolve a script-policy restriction. PowerShell 7 is available from [Microsoft's installation guide](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-windows), but installing another shell is not a guarantee that your policy permits scripts.

In your chosen PowerShell window, these read-only commands show the version and policy:

```powershell
$PSVersionTable.PSVersion
Get-ExecutionPolicy -List
```

If scripts are blocked, stop and use your administrator's approved signing/local-script workflow. Do not add an execution-policy bypass or change machine security settings just to follow this guide. This development preview does not yet include a signed packaged installer. See [Microsoft's policy explanation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies).

Open the extracted folder in File Explorer, right-click empty space → **Open in Terminal** → choose **PowerShell**. Open a new terminal after installing prerequisites. Run:

```powershell
.\setup.ps1 -Check
.\setup.ps1
```

The first command checks without installing. The second asks you to type `YES` before installing locked application dependencies. A separate question offers the pinned FFmpeg toolset needed for clip processing, thumbnails and imports. It lives in your user folder and does not change global PATH. Read each prompt; declining a component does not secretly install it later.

If Windows blocks a downloaded script, review it and use your organization’s approved PowerShell signing/local policy workflow. Do not disable security globally or run a policy bypass copied from the Internet. If `python` opens the Store or the version check fails, repair the supported Python/PATH installation and reopen Terminal. Missing Node/npm means the Node installer or PATH needs repair.

## 2. Start and connect cameras

```powershell
.\start.ps1
```

Leave this terminal running. Open **http://127.0.0.1:8765** on the PC. Create a local owner with a strong, unique passphrase; this is separate from your Blink login. The setup guide opens after first owner creation. You can also open **Settings → Open setup guide / Review setup** at any time.

Follow the guide: Privacy → Storage → Blink → Recording source. Enter Blink credentials only in the local form and complete its verification request. Select the actual recording source and explicitly enable collection. Confirm a newly created clip appears in Activity and plays. Missing clips do not become proof of successful setup; check Settings → Diagnostics.

The default archive is `%LOCALAPPDATA%\Porchlight`, outside the checkout. Never put the SQLite database/media on OneDrive or a network share. Existing data is preserved by reinstalling source dependencies. Before moving an existing archive, use the documented [backup/restore](ARCHIVE_AND_BACKUP.md) process.

### Choose your Blink hardware

In **Recording source**, choose **Camera setup** (doorbell, cameras or both) and **Sync Module type**, then explicitly **Save hardware choice**. The same controls are in Settings → Cameras & recording. Not sure and mixed setups are supported. These local preferences survive restart and guide the instructions; they never grant recording access or change your devices, account or subscription.

- **Core / original module:** no removable-storage recording; use genuinely available cloud clips or manual imports.
- **Sync Module 2:** compatible Type-A USB storage.
- **Sync Module XR / XR+:** compatible microSD storage. XR+ USB-C is for power, not storage.
- **No module:** follow your camera's requirements; cloud clips and supported live viewing are checked independently.

Prepare the card/drive and check **Local Storage** in the official Blink app. Then use Porchlight's observed module status and explicitly request local sync when eligible. A selected XR+ is not a detected storage-ready XR+. A plan/trial backup is not evidence of direct no-plan recordings; check each camera's plan coverage in mixed systems. Older XT/XT2/Indoor (1st generation) cameras do not support local storage even on a newer module. Blink access still requires internet. Sources: [Local Storage guidance](https://support.blinkforhome.com/using-your-sync-module/sync-module-2-local-storage-operation), [Sync Module 2 FAQ](https://support.blinkforhome.com/faq-sync-module-2), [XR+ FAQ](https://blink.helpjuice.com/en_US/faq-sync-module-xr-plus/sync-module-xr-plus-faq), checked 2026-10-12.

Before claiming no-plan compatibility, verify genuinely new clips and a post-restart recording using the [hardware validation gate](02_BLINK_COMPATIBILITY_AND_NO_SUBSCRIPTION.md). A manual import or daily cloud backup cannot pass that gate.

## 3. Choose AI or skip it

In the Local AI step, click **Use Porchlight without AI** to keep automatic descriptions and face scanning off. Cameras, archive, audio/video playback, thumbnails, favourites, notes and generic alerts still work. Blink-provided camera/time/source information and measured clip duration remain visible; no person/action description is invented.

Or click **Check this PC for AI**, follow the installation instructions and test a local vision model. Hardware hints are not proof it fits or runs quickly. The guide never downloads a model or modifies a shared Ollama server on its own. See [local AI setup](LOCAL_AI_SETUP.md).

## 4. Add the phone when ready

Use the Phone step and [phone setup](PHONE_SETUP.md). [Direct home HTTPS](DIRECT_HTTPS.md) supports a normal browser/home-screen app without a phone VPN when your home connection permits it. An optional [private Cloudflare tunnel backup](CLOUDFLARE_BACKUP.md) can be kept separately; that route needs an enrolled phone VPN and a verified access policy. For users without a domain, Tailscale Funnel is another test candidate, with beta/bandwidth limits. Published Cloudflare HTTP tunnels have video restrictions. Every remote route needs explicit setup and real cellular acceptance; no route is enabled by the guide.

After connecting, install from Chrome’s menu, pair notifications and test locked-screen Wi-Fi/cellular delivery and tap-to-play separately. Receiving text does not prove the phone can fetch a private thumbnail or video.

### Enable optional Web Push

On the PC, preview the separate optional installation:

```powershell
.\scripts\enable-webpush.ps1
```

If you want phone push and approve the displayed package installation, run:

```powershell
.\scripts\enable-webpush.ps1 -Install
```

Stop and start Porchlight afterward. Open your configured HTTPS address on the phone, sign in, then open **Settings → Notifications**. Allow browser notifications and pair this browser using the page controls. Send its test notification before testing a new camera event. Optionally enable descriptions; AI must complete before descriptive updates can arrive. The PC must stay awake, and encrypted messages pass through browser-vendor push services. See [Web Push](WEB_PUSH.md) for permissions, revocation and troubleshooting. Installing the home-screen icon alone does not grant notification permission.

## Everyday use

- Start: `./start.ps1`; open the PC or approved phone address.
- Stop: in a second terminal in the same checkout, `./stop.ps1`. It cooperatively stops only this Porchlight instance. A separately started tunnel has its own terminal; stop that connector with Ctrl+C. Ollama and unrelated projects are not stopped.
- Review setup: Settings → Review setup. Optional steps can be revisited.
- The PC must remain awake and connected for new imports, local analysis, remote viewing and new alerts. Porchlight does not change sleep settings automatically.

The same-PC clean dependency installation and synthetic startup/playback/restart are verified. On 2026-10-20, the owner also reported passing the new-user Windows installation, fresh backup/restore, 24–48-hour soak and listed Wi-Fi/cellular phone checks. These are owner-reported results for the tested setup; script policy remains a prerequisite, and other Windows/GPU/camera combinations are not certified. See the [release checklist](RELEASE_CHECKLIST.md).

## Testing beside an existing installation

A second source checkout does **not** automatically create a separate archive: the default Windows user profile is shared. For an isolated test, use a new source folder, a separate `PORCHLIGHT_DATA_ROOT`, a different `PORCHLIGHT_PORT` and a separate process-local `LOCALAPPDATA` for media tools/phone configuration. Set these only in the dedicated test terminal, before setup/start, and use that same terminal environment to stop the test. Keep every test path outside your real archive and the source checkout.

The clean-install validation used new dependency environments and empty caches, synthetic data only, and no Blink login. It left the real app running and checked that its original history remained present. Do not connect a second test actor to the same Blink account while the real app is connected. Your ordinary installation continues to use its existing profile and desktop launcher.

## Update safely

1. Stop Porchlight with `.\stop.ps1`. Back up the archive to a **new empty local destination** outside the checkout:

   ```powershell
   .\backup.ps1 -Destination C:\PorchlightBackups\before-update
   ```

2. For a Git installation, check `git status` and preserve your own source edits before running `git pull --ff-only`. For a ZIP installation, extract the new source to a new folder; keep the old checkout until the new version works. Neither route should replace the separately stored runtime profile.
3. Run `.\setup.ps1 -Check`, then `.\setup.ps1` to review/install the new locked dependencies and build the interface. Start with `.\start.ps1` and verify login, recent clips and diagnostics. Do not start two instances against the same profile.
4. Keep the backup until verification is complete. Database migrations may prevent simply running old code against an updated profile. To roll back, follow [backup/restore](ARCHIVE_AND_BACKUP.md), restoring to a **new** profile rather than overwriting the live archive.

Restoring begins with a read-only validation:

```powershell
.\restore.ps1 -Backup C:\PorchlightBackups\before-update -Destination C:\PorchlightRestored
```

Only add `-Apply` after reviewing that validation and choosing to create the new destination. Reconnect credentials separately and review paused automation after restore. Backups contain private footage and notes; protect them and never commit them.

## Common problems

| Symptom | Check |
|---|---|
| PC page will not open | Keep the `start.ps1` terminal open; read its error. Confirm no second instance is already running. The default is HTTP on loopback port 8765. |
| Configure FFmpeg | Accept the separate media-tools offer in setup, or configure supported executables as documented. Stop/start after installation. Diagnostics should detect both FFmpeg and ffprobe. |
| New clips are delayed | Check Cameras & recording for enabled sync and its next eligible check. Cloud discovery defaults to 60 seconds; downloads, AI and upstream availability add delay. Temporary errors recover automatically with backoff and a 15-minute cooldown after repeated failures. |
| Sign-in required / changed account | Complete Blink authentication in the local form, then explicitly resume recording work. Repeated retries cannot repair an expired login. |
| Source media expired | Blink no longer provides that old clip. It stays unavailable; healthy new-clip discovery continues. |
| Card has data but the local feed is empty | Paid-plan daily backups differ from playable Local Storage clips. Confirm a genuinely new playable clip in Blink's local list before testing Porchlight retrieval. |
| AI unavailable or slow | Choose Use Porchlight without AI; recording collection continues. Review the local AI guide before installing a different model. |
| Phone says unavailable | First open the exact HTTPS address in Chrome. Check that the PC and proxy are running, the certificate is trusted and your chosen network route works. A home-screen install cannot repair reachability. |
| Notification has text but no image | Expand it, confirm phone login/reachability and refresh the notification worker using Settings. Android/browser image display varies; an encrypted push acknowledgement does not prove image display. |

For help, share versions and redacted error codes. Do not attach private recordings, face samples, databases, credentials, certificate keys or unredacted diagnostics to public issues.
