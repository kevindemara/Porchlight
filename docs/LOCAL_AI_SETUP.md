# Optional local AI, step by step

You can complete Porchlight setup without AI. **Use Porchlight without AI** in the guide pauses automatic descriptions and face scanning, keeping existing results/profiles. Collection, playback, clip metadata and generic activity alerts continue. Face recognition is a separate opt-in installation and reviewed enrollment; see [face setup](FACE_DETECTION.md).

## Check before downloading

Settings → AI → **Check this PC for AI** reads RAM, CPU threads and, when available, NVIDIA memory. These are conservative Porchlight suggestions, not official model minimums:

| Observed hardware | Starting choice |
|---|---|
| Below approximately 16 GiB RAM | Skip AI first |
| Approximately 16 GiB RAM and 8 GiB NVIDIA memory | Try `qwen3-vl:4b`, Light |
| At least approximately 24 GiB RAM and 12 GiB NVIDIA memory | Try `qwen3-vl:8b`, Balanced |
| RAM sufficient but NVIDIA memory unknown/small | Skip, or test a smaller model; CPU/other supported GPUs may work slowly |

No detected NVIDIA GPU does not mean another GPU is unsupported. Memory is not added across GPUs. Running games, other models and other GPU apps reduce available capacity. The check does not install, benchmark, unload models or alter services.

## Install and keep inference local

1. Download and run the [official Windows Ollama installer](https://ollama.com/download/windows). Existing Ollama users should keep their installation and models. Ollama’s [Windows documentation](https://docs.ollama.com/windows) explains OS/GPU compatibility and installation space; models require additional space beyond the installer.
2. In PowerShell in the Porchlight checkout, preview the local-only change, then apply it only if you agree:

   ```powershell
   .\scripts\setup-local-ai.ps1 -LocalOnly
   .\scripts\setup-local-ai.ps1 -LocalOnly -Apply
   ```

   The helper preserves other settings and makes a private backup before changing an existing file. It does not restart Ollama or change automatic Porchlight AI. For manual setup instead, open `%USERPROFILE%\.ollama\server.json`; create it with this content if absent, or add the property while preserving other settings:

   ```json
   { "disable_ollama_cloud": true }
   ```

   Make sure the file is `server.json`, not `server.json.txt`. This is an explicitly chosen shared-server change: it disables cloud models/search for other applications using Ollama too. The alternative `OLLAMA_NO_CLOUD=1` is documented in the [Ollama FAQ](https://docs.ollama.com/faq); do not overwrite an existing global configuration blindly.
3. Quit Ollama from its system-tray menu, then reopen it. Keep its default **localhost:11434** binding. Never tunnel/expose Ollama or change it to `0.0.0.0` for Porchlight.
4. Review [4b model details/licence](https://ollama.com/library/qwen3-vl:4b) or [8b model details/licence](https://ollama.com/library/qwen3-vl:8b), then run **one** download command in PowerShell:

   ```powershell
   .\scripts\setup-local-ai.ps1 -Model qwen3-vl:4b       # Preview
   .\scripts\setup-local-ai.ps1 -Model qwen3-vl:4b -Apply # Explicit download
   # Or, for the larger candidate:
   # .\scripts\setup-local-ai.ps1 -Model qwen3-vl:8b -Apply
   ```

   With `-Apply`, the helper runs `ollama pull` for that fixed candidate. This contacts the model registry to download weights; private clips are not sent there. Review free space on Ollama’s actual model drive. Porchlight’s archive-space reading does not establish space on a different model drive. No model is bundled or automatically installed.

## Test before enabling

Back in Settings → AI:

1. Click **Check local models**; select the downloaded vision model.
2. Click **Test with a synthetic image**. This checks local-only runtime metadata and image handling on a generated colour image; it does not analyze private footage. First load may take up to two minutes.
3. Only after a passing test and **Local-only server confirmed**, select the suggested workload, tick **Analyze new recordings automatically** and **Save settings**.
4. Check a representative clip locally. The colour test is not evidence of scene accuracy or acceptable continuous throughput. If analysis is too slow, use Light or leave it disabled. Porchlight keeps the clip even when analysis fails.

Connection failure: open Ollama and recheck. Local-only not confirmed: review the JSON/property, restart Ollama and recheck. Model absent: wait for `ollama pull` to finish. Text-only/cloud model: choose a local vision model. Insufficient memory or competing models: leave automatic AI off; Porchlight never unloads unrelated models automatically.

Saved face names and Qwen descriptions are optional local results. Without them, Activity presents the camera, recording timestamp/source, duration and thumbnail honestly. Blink’s official app may have smart descriptions that the unofficial clip API does not supply; Porchlight does not bypass a paid feature to obtain them.
