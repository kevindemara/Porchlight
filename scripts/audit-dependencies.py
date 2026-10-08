"""Read-only advisory check of public lockfile names/versions, without installing tools.

Default is a local preview. --online sends only dependency metadata to OSV.
API documentation: https://google.github.io/osv.dev/post-v1-querybatch/
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def packages(include_push: bool) -> list[dict[str, object]]:
    result: dict[tuple[str, str, str], dict[str, object]] = {}
    locks = [ROOT / "requirements.lock"]
    if include_push:
        locks.append(ROOT / "requirements.push.lock")
    for lock in locks:
        for line in lock.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)(?:;.*)?", line)
            if not match:
                raise ValueError("Only exact named package pins are supported.")
            name, version = match.groups()
            result["PyPI", name, version] = {
                "package": {"ecosystem": "PyPI", "name": name},
                "version": version,
            }
    lock = json.loads((ROOT / "apps/web/package-lock.json").read_text())
    for path, data in lock["packages"].items():
        if not path:
            continue
        name, version = path.rsplit("node_modules/", 1)[-1], data.get("version")
        if (
            not re.fullmatch(r"(?:@[a-zA-Z0-9_.-]+/)?[a-zA-Z0-9_.-]+", name)
            or not isinstance(version, str)
            or not re.fullmatch(r"[A-Za-z0-9_.+-]+", version)
        ):
            raise ValueError("Unsupported lockfile package metadata.")
        result["npm", name, version] = {
            "package": {"ecosystem": "npm", "name": name},
            "version": version,
        }
    return list(result.values())


def audit(queries: list[dict[str, object]]) -> dict[str, object]:
    pending = list(enumerate(queries))
    findings: dict[int, set[str]] = {}
    for _ in range(5):
        if not pending:
            break
        request = urllib.request.Request(
            "https://api.osv.dev/v1/querybatch",
            data=json.dumps({"queries": [query for _, query in pending]}).encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Porchlight-dependency-review/1",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(8 * 1024**2 + 1)
            if len(raw) > 8 * 1024**2:
                raise ValueError("Advisory response exceeded the safe size limit.")
            results = json.loads(raw)["results"]
        if not isinstance(results, list) or len(results) != len(pending):
            raise ValueError("Incomplete advisory response.")
        remaining = []
        for (index, query), result in zip(pending, results, strict=True):
            for vulnerability in result.get("vulns", []):
                identifier = vulnerability["id"]
                if not isinstance(identifier, str) or not re.fullmatch(
                    r"[A-Za-z0-9_-]{1,128}", identifier
                ):
                    raise ValueError("Unsupported advisory identifier.")
                findings.setdefault(index, set()).add(identifier)
            if result.get("next_page_token"):
                remaining.append((index, {**query, "page_token": result["next_page_token"]}))
        pending = remaining
    if pending:
        raise ValueError("Advisory pagination exceeded the safe limit; review is incomplete.")
    return {
        "format": "porchlight-dependency-advisory-review-v1",
        "checked_at": datetime.now(UTC).isoformat(),
        "source": "https://api.osv.dev/v1/querybatch",
        "package_versions_checked": len(queries),
        "affected_package_versions": len(findings),
        "findings": [
            {**queries[index], "advisories": sorted(identifiers)}
            for index, identifiers in sorted(findings.items())
        ],
        "scope": "Exact lockfile versions, including development and platform-optional packages. "
        "Known advisory matches only; not a security or licence certification.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--include-push-candidates", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        queries = packages(args.include_push_candidates)
        if not args.online:
            print(
                json.dumps(
                    {"preview": True, "package_versions": len(queries), "network_requested": False}
                )
            )
            return 0
        report = audit(queries)
        report["includes_uninstalled_push_candidates"] = args.include_push_candidates
        if args.output:
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
        return 1 if report["affected_package_versions"] else 0
    except Exception:
        print(json.dumps({"completed": False, "code": "ADVISORY_REVIEW_UNAVAILABLE"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
