import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from porchlight.config import ROOT, Config

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native Windows setup helpers")


def run_script(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            shutil.which("pwsh.exe") or "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "scripts/configure-phone.ps1"),
            *args,
        ],
        env={
            **os.environ,
            "LOCALAPPDATA": str(tmp_path / "local"),
            "USERPROFILE": str(tmp_path / "user with [spaces]"),
        },
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.mark.parametrize(
    "origin",
    [
        "http://porchlight.example.com",
        "https://127.0.0.1",
        "https://10.0.0.1",
        "https://*.example.com",
        "https://a..example.com",
        "https://example.com:444",
        "https://name:secret@example.com",
        "https://example.com/private",
        "https://example.com?token=synthetic",
        "https://example.com#live",
    ],
)
def test_invalid_phone_origins_do_not_write_configuration(tmp_path: Path, origin: str) -> None:
    result = run_script(tmp_path, "-Origin", origin, "-Apply")
    assert result.returncode != 0
    assert not (tmp_path / "local").exists()


def test_phone_preview_apply_conflict_disable_and_private_tunnel_routing(tmp_path: Path) -> None:
    result = run_script(tmp_path, "-Origin", "https://porchlight.example.com")
    assert result.returncode == 0 and "No changes made" in result.stdout
    assert not (tmp_path / "local").exists()
    tunnel_id = "3f501610-0c26-4a91-9cce-a2b141d6c8e1"
    credentials = tmp_path / "user with [spaces]" / ".cloudflared" / f"{tunnel_id}.json"
    credentials.parent.mkdir(parents=True)
    credentials.write_text("{}", encoding="utf-8")  # Synthetic credential-file presence only.
    result = run_script(
        tmp_path, "-Origin", "https://Porchlight.example.com/", "-TunnelId", tunnel_id, "-Apply"
    )
    assert result.returncode == 0, result.stderr
    import json

    folder = tmp_path / "local" / "PorchlightSetup"
    saved = json.loads((folder / "phone-access.json").read_text(encoding="utf-8-sig"))
    assert saved == {"version": 1, "public_origin": "https://porchlight.example.com"}
    assert Config(data_root=tmp_path / "profile", public_origin=saved["public_origin"])
    routing = (folder / "tunnel.yml").read_text(encoding="utf-8-sig")
    assert "http://127.0.0.1:8765" in routing and "http_status:404" in routing
    assert "httpHostHeader: porchlight.example.com" in routing
    assert "11434" not in routing and "5174" not in routing
    assert json.dumps(str(credentials)) in routing
    before = (folder / "phone-access.json").read_bytes()
    conflict = run_script(tmp_path, "-Origin", "https://other.example.com", "-Apply")
    assert conflict.returncode != 0 and (folder / "phone-access.json").read_bytes() == before
    assert run_script(tmp_path, "-Disable").returncode == 0
    assert (folder / "phone-access.json").exists()
    assert run_script(tmp_path, "-Disable", "-Apply").returncode == 0
    assert not (folder / "phone-access.json").exists()
    assert credentials.is_file()  # Never removes a connector's credentials.


@pytest.mark.parametrize("check", [True, False])
def test_beginner_setup_checks_or_declines_without_installing(tmp_path: Path, check: bool) -> None:
    project = tmp_path / "checkout with [spaces]"
    project.mkdir()
    for filename in ("setup.ps1", "bootstrap.ps1"):
        shutil.copyfile(ROOT / filename, project / filename)
    harness = tmp_path / "harness.ps1"
    harness.write_text(
        """param([string]$Script, [switch]$Check)
$ErrorActionPreference = 'Stop'
function python {
    if ($args[0] -ne '-c') { throw 'Installation forbidden' }
    $global:LASTEXITCODE=0; '3.12.10'
}
function node {
    if ($args[0] -ne '-p') { throw 'Installation forbidden' }
    $global:LASTEXITCODE=0; '24.19.0'
}
function npm.cmd { throw 'Installation forbidden' }
function Read-Host { 'NO' }
& $Script -Check:$Check
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
            str(project / "setup.ps1"),
            *(["-Check"] if check else []),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert {path.name for path in project.iterdir()} == {"setup.ps1", "bootstrap.ps1"}
