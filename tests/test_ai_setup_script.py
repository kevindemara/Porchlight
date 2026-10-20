import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from porchlight.config import ROOT

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows local AI helper")


def run_ai_script(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            shutil.which("pwsh.exe") or "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "scripts/setup-local-ai.ps1"),
            *args,
        ],
        env={**os.environ, "USERPROFILE": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_local_only_preview_preserves_settings_and_apply_backs_up_without_restart(
    tmp_path: Path,
) -> None:
    folder = tmp_path / ".ollama"
    folder.mkdir()
    server = folder / "server.json"
    original = '{"unrelated":{"keep":17},"disable_ollama_cloud":false}'
    server.write_text(original, encoding="utf-8")
    assert run_ai_script(tmp_path, "-LocalOnly").returncode == 0
    assert server.read_text(encoding="utf-8") == original and len(list(folder.iterdir())) == 1
    result = run_ai_script(tmp_path, "-LocalOnly", "-Apply")
    assert result.returncode == 0, result.stderr
    assert json.loads(server.read_text(encoding="utf-8")) == {
        "unrelated": {"keep": 17},
        "disable_ollama_cloud": True,
    }
    backups = list(folder.glob("server.before-porchlight-*.json"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == original
    assert not server.read_bytes().startswith(b"\xef\xbb\xbf")
    assert run_ai_script(tmp_path, "-LocalOnly", "-Apply").returncode == 0
    assert list(folder.glob("server.before-porchlight-*.json")) == backups


@pytest.mark.parametrize("content", ["[1, 2]", "null", "not valid JSON"])
def test_invalid_ollama_configuration_is_not_replaced(tmp_path: Path, content: str) -> None:
    folder = tmp_path / ".ollama"
    folder.mkdir()
    server = folder / "server.json"
    server.write_text(content, encoding="utf-8")
    assert run_ai_script(tmp_path, "-LocalOnly", "-Apply").returncode != 0
    assert server.read_text(encoding="utf-8") == content
    assert len(list(folder.iterdir())) == 1


def test_model_actions_are_preview_by_default_and_reject_arbitrary_models(tmp_path: Path) -> None:
    assert run_ai_script(tmp_path, "-Model", "qwen3-vl:4b").returncode == 0
    assert not (tmp_path / ".ollama").exists()
    assert run_ai_script(tmp_path, "-Model", "arbitrary-cloud-model", "-Apply").returncode != 0

    harness = tmp_path / "fake-model-download.ps1"
    harness.write_text(
        """param([string]$Script)
function ollama {
    if ($args.Count -ne 2 -or $args[0] -ne 'pull' -or $args[1] -ne 'qwen3-vl:4b') {
        throw 'Unexpected model command'
    }
    $global:LASTEXITCODE = 0
    Write-Output 'SYNTHETIC_MODEL_PULL_ONLY'
}
& $Script -Model 'qwen3-vl:4b' -Apply
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            shutil.which("pwsh.exe") or "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(harness),
            "-Script",
            str(ROOT / "scripts/setup-local-ai.ps1"),
        ],
        env={**os.environ, "USERPROFILE": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0 and "SYNTHETIC_MODEL_PULL_ONLY" in result.stdout
    assert not (tmp_path / ".ollama").exists()
