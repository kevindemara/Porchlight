"""Record this Windows development environment and preserve installed licence notices."""

import json
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
packages = sorted(
    (
        item
        for item in distributions()
        if item.metadata["Name"].lower() not in {"pip", "porchlight"}
    ),
    key=lambda item: item.metadata["Name"].lower(),
)
lock = []
rows = []
for package in packages:
    name = package.metadata["Name"]
    marker = "; sys_platform == 'win32'" if name.lower() == "pywin32" else ""
    # Installing the optional detector must not make it part of every bootstrap.
    if name.lower() not in {"opencv-python-headless", "numpy"}:
        lock.append(f"{name}=={package.version}{marker}\n")
    licence = package.metadata.get("License-Expression") or package.metadata.get(
        "License", "Unspecified"
    )
    licence = licence.splitlines()[0][:160]
    rows.append(f"| {name} | {package.version} | {licence.replace('|', '/')} |")
    for entry in package.files or []:
        filename = str(entry).replace("\\", "/")
        if ".dist-info/" not in filename:
            continue
        relative = filename.split(".dist-info/", 1)[1]
        if relative.startswith("licenses/") or relative.upper().startswith(
            ("LICENSE", "COPYING", "NOTICE")
        ):
            destination = ROOT / "notices/python" / name / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(Path(package.locate_file(entry)).read_bytes())
(ROOT / "requirements.lock").write_text("".join(lock), encoding="utf-8")
frontend = json.loads((ROOT / "apps/web/package-lock.json").read_text())
js_rows = []
for path, metadata in sorted(frontend["packages"].items()):
    if not path:
        continue
    name = path.rsplit("node_modules/", 1)[-1]
    js_rows.append(
        f"| {name} | {metadata.get('version', 'unknown')} | "
        f"{metadata.get('license', 'Unspecified')} |"
    )
    package_root = ROOT / "apps/web" / path
    for entry in package_root.glob("*"):
        if entry.is_file() and entry.name.upper().startswith(
            ("LICENSE", "LICENCE", "COPYING", "NOTICE")
        ):
            destination = ROOT / "notices/frontend" / name / entry.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(entry.read_bytes())
(ROOT / "docs/DEPENDENCY_INVENTORY.md").write_text(
    "# Installed dependency inventory\n\nRecorded 2026-10-06. "
    "Package metadata is an intake record; public distribution still requires the release review. "
    "Installed licence files are retained in `notices/`. "
    "The Windows lock includes development tools. "
    "FFmpeg and model weights are external and are not bundled.\n\n"
    "## Python\n\n| Package | Exact version | Declared licence |\n|---|---|---|\n"
    + "\n".join(rows)
    + "\n\n## Frontend, including build/test dependencies\n\n"
    "| Package | Exact version | Declared licence |\n|---|---|---|\n"
    + "\n".join(js_rows)
    + "\n",
    encoding="utf-8",
)
