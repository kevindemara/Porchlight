# 11 · Windows setup and operations

## Existing environment

Use the existing Windows Ollama installation and its current model directory. The target GPU/RAM information is an assumption from the owner's prior setup; verify locally. Do not reinstall Ollama, reset its settings, remove models, or relocate any existing model folders.

Prefer native Windows Python for this application's first version. A WSL process does not automatically see the Windows host's loopback Ollama endpoint in every network configuration. Avoid introducing that complication as a hidden prerequisite. The optional self-hosted ntfy path may use a separately chosen container/WSL/Linux host.

## Included preflight

`scripts/preflight.ps1` is a read-only helper. It checks commands, available disk space, basic GPU information and the local Ollama version/model metadata. It does not connect to Blink, request passwords, install tools, pull models or change settings.

From the extracted folder, a normal PowerShell invocation is:

```powershell
.\scripts\preflight.ps1
```

If local execution policy blocks the script, review its text and use your established signed-script/local policy workflow. Do not globally disable Windows security policy. Its output may contain model names and system details; do not publish it unreviewed.

## M0 prerequisites Codex should resolve

Git; a supported Python version (prefer an existing compatible Python 3.12/3.13 installation); Node on a currently supported LTS release compatible with the selected frontend build tools; npm; FFmpeg and ffprobe; existing Ollama. Use a project Python virtual environment. npm avoids assuming pnpm is already installed on this PC. If tools are absent, provide specific official installation steps and request the necessary local action rather than silently changing the machine.

Pin actual working package versions with lockfiles. Do not invent a tested runtime matrix. Include timezone data for Python on Windows so `America/Toronto` works consistently.

## Script deliverables for the implemented application

These commands were required build outputs in the original specification. All scripts below are now present. Startup registration/removal is opt-in and its actual sign-in behavior remains unverified; see [local setup](LOCAL_DEVELOPMENT.md).

| Script | Behaviour |
|---|---|
| `bootstrap.ps1` | `-Check` validates runtimes without installing; ordinary explicit invocation creates project venv, installs locked dependencies and builds UI; never overwrite data |
| `dev.ps1` | Start development backend/frontend on loopback with clear ports; avoid duplicate pollers |
| `start.ps1` | Start one production backend serving built UI; show local URL and data location |
| `stop.ps1` | Graceful stop only this app's recorded process, never kill all Python/Ollama processes |
| `test.ps1` | Run unit/contracts/integration/UI tests; return nonzero on failure |
| `backup.ps1` | Consistent DB/media backup with manifest/checksums and secret inclusion policy |
| `restore.ps1` | Validate backup to a staging location, preview, require explicit confirmation |
| `install-startup.ps1` | Optional scheduled task/service setup under the intended user, never automatic |
| `uninstall-startup.ps1` | Remove only Porchlight startup registration; keep data unless explicitly deleted |

Scripts should handle paths with spaces, fail usefully, verify exit codes and avoid requiring administrator access for ordinary operation. Never use hardcoded passwords in a scheduled task command.

## First use after implementation

Open the displayed localhost URL, claim the one-time local setup, create the administrator, choose a media folder, and complete the Blink/recording-source check. Then select/test a local vision model, import an owner-controlled clip, and verify the full path. Finally configure an actual phone notification transport and trusted remote/local HTTPS as needed.

Keep the distinction between successful login, clip retrieval, AI and phone delivery visible. A single green “setup finished” label must not conceal an untested no-plan recording path.

## Suggested starting settings

Application host `127.0.0.1`; port `8765`; local timezone `America/Toronto`; background discovery 120 seconds; one AI job; up to six frames; local model only; original playback muted; cloud inference off; live view off; no remote source deletion; ordinary retention 30 days; archive soft budget 50 GiB; free-space reserve 5 GiB. Explain/confirm retention in setup before it deletes user data.

Use `examples/settings.example.json` as a nonsecret specification. The implementation must validate settings and expose actual effective values, not silently accept unknown keys.

## Startup and availability

Start manually first. Optional auto-start must be explicit. A task running under the wrong user may not access the vault, media disk or user-installed Ollama. Coordinate the app and Ollama startup with readiness checks and bounded retries, not a guessed fixed sleep.

The PC must be awake for new downloads, analysis and alerts. Explain that sleep/reboot/Windows updates interrupt service. Never change the owner's power settings automatically. Provide a last-worker-heartbeat indicator and a catch-up summary after resuming. Only recordings still available upstream can be recovered.

## Backups and restore

Default backup is local, with no cloud upload. Pause writes or use SQLite's consistent backup procedure, snapshot media references, copy required assets, and include schema/app versions and checksums. Do not simply copy the `.db` while ignoring WAL. [T3](15_SOURCES_AND_VERSIONING.md#t3)

By default exclude the OS-bound vault and require Blink reauthentication after a restore. Restoring another owner's sessions/push registrations is not automatic. A restored DB must not resend old outbox notifications. Run integrity checks and a dry-run startup before replacing working data.

## Troubleshooting

**Ollama unreachable:** confirm the existing app is running and query loopback. Do not bind to all interfaces as the first fix. **No vision model:** inspect capabilities and offer a specific local model download. **Out of memory/slow AI:** reduce frames/context, pause historical work, or select a smaller locally approved model; do not terminate the user's other work.

**Blink connects but has no clips:** inspect recording mode, entitlement, storage health, timestamps and source-specific discovery. **401/reauth:** show the local reconnect flow, not retries every second. **429:** back off and inspect request counts, duplicate processes and other integrations.

**Phone receives nothing:** distinguish permission, HTTPS/secure-context, endpoint, device OS restrictions, server availability and remote reachability. **Phone receives a notification but cannot open video:** the delivery relay is reachable but the private home server may not be.

**Storage problems:** verify selected disk exists, is local/writeable, has free space and is not a OneDrive/network path. Do not format or repartition any disk.

## Native development readiness

The development launcher passes a unique GUID to the backend, waits up to 30 seconds for its matching process marker plus native liveness, then starts Vite at 127.0.0.1:5174. The actual server PID may differ from the Windows venv launcher's PID. Cleanup uses the matching instance stop signal, never a broad process kill. SSE streams observe the cooperative closing signal; a native empty-profile test verifies shutdown with a connected client.

Runtime storage also rejects mapped drives reported as DRIVE_REMOTE by Windows [GetDriveTypeW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdrivetypew). This check is read-only. No task, policy, firewall, service or power setting was changed for these checks.
