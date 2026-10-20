# Set up Porchlight on Windows

Start with a working camera archive. AI and phone access are optional additions; neither is required to save and watch available clips. This is a source installation, not yet a packaged one-click installer.

## 1. Prepare the PC

Use a local folder outside OneDrive, such as `C:\Apps\Porchlight`. Download/extract the repository there. Keep the PC’s normal Windows user account for setup and running the app; its encrypted credentials belong to that user.

Install these prerequisites if missing:

- [Python for Windows](https://www.python.org/downloads/windows/), version **3.12 through 3.14**. Tick **Add Python to PATH** in its installer. The development build was tested with 3.12.10.
- [Node.js with npm](https://nodejs.org/en/download), a supported release satisfying **22.12 or newer**. The development build was tested with 24.19.0. Node builds the interface; it is not the production web server.

Ollama, Docker, a cloud database, a paid AI API and a Cloudflare account are **not** prerequisites. Recording access depends on the Blink hardware/storage/account; do not cancel a plan based on successful paid-cloud imports.

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

## Everyday use

- Start: `./start.ps1`; open the PC or approved phone address.
- Stop: in a second terminal in the same checkout, `./stop.ps1`. It cooperatively stops only this Porchlight instance. A separately started tunnel has its own terminal; stop that connector with Ctrl+C. Ollama and unrelated projects are not stopped.
- Review setup: Settings → Review setup. Optional steps can be revisited.
- The PC must remain awake and connected for new imports, local analysis, remote viewing and new alerts. Porchlight does not change sleep settings automatically.

Public release still needs the [release checklist](RELEASE_CHECKLIST.md), a real clean dependency installation and actual remote-device acceptance. The development PC passing tests is not proof that every Windows/GPU/camera combination works.
