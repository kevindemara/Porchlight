"""Local-only working-tree and reachable Git history review; never print matching values.

Findings need human review: examples, synthetic credentials and third-party notices
can match. An empty report is not a guarantee that no secret exists.
"""

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = {
    "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    "provider_token": (
        rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[A-Z0-9]{16})\b"
    ),
    "windows_profile": (
        rb"[A-Za-z]:[\\/]+Users[\\/]+(?!Public\b|example\b|USERNAME\b)[A-Za-z0-9_. -]+"
    ),
    "dpapi_blob": rb"AQAAANCMnd8BFdERjHoAwE[A-Za-z0-9+/=]{64,}",
    "credential_literal": (
        rb"(?i)(?:password|client_secret|api_key|access_token|refresh_token)"
        rb"\s*[=:]\s*[\"'][^\"'\r\n]{16,}[\"']"
    ),
}
SENSITIVE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".dpapi",
    ".mp4",
    ".webm",
    ".wav",
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def inspect(data: bytes, rules: dict[str, bytes]) -> list[dict[str, object]]:
    findings = []
    if b"\0" in data:
        return findings
    for category, pattern in rules.items():
        for match in re.finditer(pattern, data):
            findings.append({"category": category, "line": data.count(b"\n", 0, match.start()) + 1})
    return findings


def review(private_patterns: Path | None) -> dict[str, object]:
    rules = dict(RULES)
    if private_patterns:
        # JSON category -> regex. The file and patterns never enter the report.
        rules.update(
            {
                key: value.encode()
                for key, value in json.loads(private_patterns.read_text(encoding="utf-8")).items()
            }
        )
    findings: list[dict[str, object]] = []
    binaries: set[str] = set()
    current = git("ls-files", "-z").decode().split("\0")
    for name in filter(None, current):
        path = ROOT / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        findings.extend(
            {"scope": "working_tree", "path": name, **row} for row in inspect(data, rules)
        )
        if path.suffix.lower() in SENSITIVE_SUFFIXES:
            findings.append(
                {"scope": "working_tree", "path": name, "category": "sensitive_file_type"}
            )
        if b"\0" in data:
            binaries.add(name)
    objects = git("rev-list", "--objects", "--all").decode().splitlines()
    blobs = 0
    process = subprocess.Popen(
        ["git", "-C", str(ROOT), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert process.stdin and process.stdout
    try:
        for entry in objects:
            oid, _, name = entry.partition(" ")
            process.stdin.write((oid + "\n").encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            size = int(header[2])
            data = process.stdout.read(size)
            assert process.stdout.read(1) == b"\n"
            if header[1] != "blob":
                continue
            blobs += 1
            findings.extend(
                {"scope": "history", "blob": oid, "path": name, **row}
                for row in inspect(data, rules)
            )
            if Path(name).suffix.lower() in SENSITIVE_SUFFIXES:
                findings.append(
                    {
                        "scope": "history",
                        "blob": oid,
                        "path": name,
                        "category": "sensitive_file_type",
                    }
                )
            if b"\0" in data:
                binaries.add(name)
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": "Tracked working files and blobs reachable from all local Git refs; no network.",
        "tracked_files": len([name for name in current if name]),
        "history_blobs": blobs,
        "findings": findings,
        "binary_paths": sorted(binaries),
        "limits": "Pattern review requires manual triage. Unreachable objects, remote-only refs, "
        "GitHub issues/releases/artifacts and unknown secret formats are outside this scan.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-patterns", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = review(args.private_patterns)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    counts = Counter(str(row["category"]) for row in report["findings"])
    print(
        json.dumps(
            {
                "tracked_files": report["tracked_files"],
                "history_blobs": report["history_blobs"],
                "review_categories": counts,
                "binary_paths": report["binary_paths"],
            }
        )
    )
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
