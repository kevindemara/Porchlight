import importlib.util
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
