import hashlib
import importlib.util
import json
from pathlib import Path


def test_repository_audit_reports_locations_without_secret_values() -> None:
    spec = importlib.util.spec_from_file_location(
        "repository_audit", Path(__file__).parents[1] / "scripts/audit-repository.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    secret = b"ghp_" + b"s" * 36
    findings = module.inspect(b"safe\n" + secret, module.RULES)
    assert findings == [{"category": "provider_token", "line": 2}]
    assert secret.decode() not in str(findings)
    assert module.inspect(b"binary\0" + secret, module.RULES) == []


def test_retained_upstream_notices_match_recorded_provenance() -> None:
    root = Path(__file__).parents[1]
    records = json.loads((root / "docs/NOTICE_SOURCES.json").read_text(encoding="utf-8"))["records"]
    identities = set()
    for record in records:
        identity = (record["package"], record["version"])
        assert identity not in identities
        identities.add(identity)
        notice = (root / record["retained_file"]).read_bytes()
        assert len(notice) == record["bytes"]
        assert hashlib.sha256(notice).hexdigest() == record["sha256"]
    uri = next(record for record in records if record["package"] == "uri-js-replace")
    assert uri["verified_upstream_license"] == "MIT-0"
    assert len(uri["verified_installed_files"]) == 8
