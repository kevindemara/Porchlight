"""Windows task scripts are exercised with in-memory cmdlet doubles, never registered."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from porchlight.config import ROOT, Config


def startup_plan(config: Config) -> dict:
    spec = importlib.util.spec_from_file_location("startup_plan", ROOT / "scripts/startup-plan.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.plan(config))


def test_startup_plan_is_stable_and_does_not_create_data(config: Config) -> None:
    first = startup_plan(config)
    assert first == startup_plan(config)
    changed = startup_plan(Config(data_root=config.data_root.with_name("another profile")))
    assert first["task_name"] != changed["task_name"]
    assert first["data_root"] == str(config.data_root)
    assert first["public_origin"] is None and first["port"] == 8765
    assert not config.data_root.exists()
    with pytest.raises(ValueError):
        startup_plan(Config(data_root=Path(config.data_root.anchor)))


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows task-script boundary")
def test_task_preview_apply_idempotency_and_ownership_use_only_cmdlet_doubles(
    tmp_path: Path,
) -> None:
    harness = ROOT / "tests/fixtures/startup-cmdlet-doubles.ps1"
    completed = subprocess.run(
        [
            shutil.which("pwsh.exe") or "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(harness),
            "-Repository",
            str(ROOT),
            "-DataRoot",
            str(tmp_path / "profile with [literal] spaces"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    line = next(line for line in completed.stdout.splitlines() if line.startswith("RESULT "))
    assert json.loads(line[7:]) == {"registered": 1, "removed": 1, "passed": True}
