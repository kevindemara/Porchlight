import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from porchlight.config import ROOT


@pytest.mark.skipif(sys.platform != "win32", reason="Native PowerShell bootstrap boundary")
@pytest.mark.parametrize(
    "python_version,node_version,passed",
    [
        ("3.12.10", "24.19.0", True),
        ("3.14.0", "22.12.0", True),
        ("3.11.9", "24.19.0", False),
        ("3.15.0", "24.19.0", False),
        ("3.12.10", "22.11.0", False),
        ("3.12.10", "21.0.0", False),
        ("3.12.10", "20.18.0", False),
    ],
)
def test_bootstrap_preflight_checks_runtimes_without_any_installation(
    tmp_path: Path, python_version: str, node_version: str, passed: bool
) -> None:
    project = tmp_path / "clean project with [literal] spaces"
    project.mkdir()
    script = project / "bootstrap.ps1"
    shutil.copyfile(ROOT / "bootstrap.ps1", script)
    harness = tmp_path / "runtimes.ps1"
    harness.write_text(
        """param([string]$Bootstrap, [string]$FakePython, [string]$FakeNode)
$ErrorActionPreference = 'Stop'
function python {
    if ($args[0] -ne '-c') { throw 'Unexpected Python installation call.' }
    $global:LASTEXITCODE = 0
    Write-Output $FakePython
}
function node {
    if ($args[0] -ne '-p') { throw 'Unexpected Node call.' }
    $global:LASTEXITCODE = 0
    Write-Output $FakeNode
}
function npm.cmd { throw 'No npm installation is allowed during preflight.' }
& $Bootstrap -Check
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
            "-Bootstrap",
            str(script),
            "-FakePython",
            python_version,
            "-FakeNode",
            node_version,
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert (result.returncode == 0) is passed, result.stdout + result.stderr
    assert list(project.iterdir()) == [script]
    if passed:
        assert "No dependencies installed" in result.stdout
    else:
        assert "requires" in result.stderr
