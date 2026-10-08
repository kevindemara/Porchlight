"""Record public package notices and advisory matches for the optional detector only."""

import importlib.metadata
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    queries = []
    for name in ("opencv-python-headless", "numpy"):
        package = importlib.metadata.distribution(name)
        queries.append({"package": {"ecosystem": "PyPI", "name": name}, "version": package.version})
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
    audit = runpy.run_path(str(ROOT / "scripts/audit-dependencies.py"))["audit"]
    report = audit(queries)  # Public names/versions only; no runtime/profile data.
    report["scope"] = (
        "Optional detector exact package versions only. Known advisory matches; "
        "not security, license or model-accuracy certification."
    )
    (ROOT / "docs/FACE_DEPENDENCY_AUDIT.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "optional_packages_checked": len(queries),
                "advisory_matches": report["affected_package_versions"],
            }
        )
    )
