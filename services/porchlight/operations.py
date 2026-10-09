"""Offline local backup/restore. Secrets and live sessions never travel in backups."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4

from porchlight import __version__
from porchlight.config import ROOT, Config
from porchlight.security.lock import InstanceLock


def contained(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if "\\" in relative or ":" in relative or parts.is_absolute() or ".." in parts.parts:
        raise ValueError("Backup contains an unsafe path.")
    if relative != "porchlight.db" and (not parts.parts or parts.parts[0] != "media"):
        raise ValueError("Backup contains an unsupported file.")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("Backup contains an unsafe path.")
    return path


def checksum(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def sanitize(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "integration_state" in tables:
        connection.execute("DELETE FROM integration_state WHERE id LIKE 'local_manifest:%'")
    for table in (
        "sessions",
        "login_attempts",
        "file_deletions",
        "push_deliveries",
        "push_devices",
        "camera_commands",
    ):
        if table in tables:
            connection.execute(f"DELETE FROM {table}")
    connection.execute(
        "DELETE FROM integration_state WHERE id IN ('blink', 'blink_live_certificates') "
        "OR id LIKE 'live_%' OR id LIKE 'push_receipt:%' "
        "OR id IN ('push_control', 'face_detection')"
    )
    for row_id, values in connection.execute('SELECT id, "values" FROM settings').fetchall():
        data = json.loads(values)
        data.update(ai_enabled=False, retention_enabled=False)
        connection.execute('UPDATE settings SET "values"=? WHERE id=?', (json.dumps(data), row_id))
    connection.execute("UPDATE recording_scans SET enabled=0")
    if "historical" in {row[1] for row in connection.execute("PRAGMA table_info(events)")}:
        connection.execute(
            "UPDATE events SET historical=1 WHERE source_type IN ('blink_cloud','blink_local')"
        )
    connection.execute(
        "UPDATE jobs SET status='failed', lease_until=NULL, safe_error='RESTORE_PAUSED' "
        "WHERE status IN ('queued','running','blocked')"
    )
    connection.execute(
        "UPDATE events SET analysis_status='analysis_failed' "
        "WHERE analysis_status IN ('queued','analyzing')"
    )
    if "notification_outbox" in tables:
        connection.execute(
            "UPDATE notification_outbox SET status='expired' "
            "WHERE status NOT IN ('transport_accepted','expired')"
        )
    connection.execute(
        "UPDATE live_captures SET state='failed', "
        "safe_error='Interrupted capture excluded from backup.' "
        "WHERE state IN ('recording','saving')"
    )
    connection.commit()

    if "notification_rules" in tables:
        for identifier, values in connection.execute(
            'SELECT id, "values" FROM notification_rules'
        ).fetchall():
            definition = json.loads(values)
            definition["enabled"] = False
            connection.execute(
                'UPDATE notification_rules SET "values"=? WHERE id=?',
                (json.dumps(definition), identifier),
            )
        connection.commit()
    if "state_changes" in tables:
        connection.execute("DELETE FROM state_changes")
        connection.commit()


def required_media(connection: sqlite3.Connection) -> set[str]:
    paths = {str(row[0]) for row in connection.execute("SELECT relative_path FROM media_assets")}
    for identifier, kind in connection.execute(
        "SELECT id, kind FROM live_captures WHERE state='ready'"
    ):
        identifier = str(UUID(identifier))
        paths.add(f"media/live-library/{identifier}{'.mp4' if kind == 'recording' else '.jpg'}")
    return paths


def safe_destination(destination: Path, data_root: Path) -> Path:
    destination = destination.expanduser().resolve()
    if (
        destination.is_relative_to(data_root.resolve())
        or data_root.resolve().is_relative_to(destination)
        or destination.is_relative_to(ROOT)
        or str(destination).startswith("\\\\")
        or "onedrive" in str(destination).lower()
    ):
        raise ValueError("Choose a new local folder outside the app data and source folders.")
    if destination.exists():
        raise ValueError("Destination already exists; choose a new folder.")
    return destination


def backup(config: Config, destination: Path) -> dict[str, Any]:
    destination = safe_destination(destination, config.data_root)
    lock = InstanceLock(config.data_root)
    lock.acquire()
    try:
        if not (config.data_root / "porchlight.db").is_file():
            raise ValueError("The application database does not exist.")
        destination.mkdir(parents=True)
        staged = destination / "porchlight.db"
        with (
            closing(sqlite3.connect(config.data_root / "porchlight.db")) as source,
            closing(sqlite3.connect(staged)) as target,
        ):
            source.backup(target)
            sanitize(target)
            paths = required_media(target)
            schema = target.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        for relative in sorted(paths):
            source_path = contained(config.data_root, relative)
            target_path = contained(destination, relative)
            if not source_path.is_file():
                raise ValueError("A referenced media file is missing; backup was not completed.")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target_path)
        files = [
            {
                "path": relative,
                "bytes": contained(destination, relative).stat().st_size,
                "sha256": checksum(contained(destination, relative)),
            }
            for relative in ["porchlight.db", *sorted(paths)]
        ]
        manifest = {
            "format": 1,
            "app_version": __version__,
            "schema_version": schema,
            "created_at": datetime.now(UTC).isoformat(),
            "secrets_included": False,
            "sessions_included": False,
            "files": files,
        }
        temporary = destination / "manifest.part"
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination / "manifest.json")
        verify(destination)
        return {
            "passed": True,
            "file_count": len(files),
            "bytes": sum(f["bytes"] for f in files),
            "secrets_included": False,
            "sessions_included": False,
        }
    finally:
        lock.release()


def verify(backup_root: Path) -> dict[str, Any]:
    backup_root = backup_root.resolve()
    manifest_path = backup_root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.stat().st_size > 16 * 1024**2:
        raise ValueError("A complete bounded backup manifest is required.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("format") != 1
        or manifest.get("secrets_included") is not False
        or manifest.get("sessions_included") is not False
    ):
        raise ValueError("Unsupported backup format or secret policy.")
    files = manifest.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= 100_000:
        raise ValueError("Invalid backup file list.")
    listed: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise ValueError("Invalid backup file entry.")
        relative = entry["path"]
        if not isinstance(relative, str) or relative in listed:
            raise ValueError("Duplicate or invalid backup file path.")
        listed.add(relative)
        path = contained(backup_root, relative)
        if (
            not path.is_file()
            or path.stat().st_size != entry["bytes"]
            or checksum(path) != entry["sha256"]
        ):
            raise ValueError("Backup checksum verification failed.")
    if "porchlight.db" not in listed:
        raise ValueError("Backup database is missing.")
    database = contained(backup_root, "porchlight.db")
    with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as connection:
        if (
            connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            or connection.execute("PRAGMA foreign_key_check").fetchone()
        ):
            raise ValueError("Backup database integrity check failed.")
        if (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            != manifest["schema_version"]
        ):
            raise ValueError("Backup schema does not match its manifest.")
        if required_media(connection) | {"porchlight.db"} != listed:
            raise ValueError("Backup media manifest does not match the database.")
        if connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]:
            raise ValueError("Backup must not include active sessions.")
    return dict(manifest)


def restore(backup_root: Path, destination: Path, *, apply: bool = False) -> dict[str, Any]:
    manifest = verify(backup_root)
    config = Config(data_root=destination)
    if destination.resolve().is_relative_to(
        backup_root.resolve()
    ) or backup_root.resolve().is_relative_to(destination.resolve()):
        raise ValueError("Choose a destination separate from the backup.")
    if config.data_root.exists():
        raise ValueError(
            "Restore requires a new destination folder; existing data is never replaced."
        )
    result = {
        "passed": True,
        "applied": apply,
        "file_count": len(manifest["files"]),
        "requires_app_sign_in": True,
        "requires_blink_reauthentication": True,
        "automatic_ai": False,
        "automatic_retention": False,
    }
    if not apply:
        return result
    # Copy into an app-created sibling, then promote only after verification/migration.
    stage = config.data_root.with_name(f"{config.data_root.name}.restore-{uuid4()}")
    stage.mkdir(parents=True)
    for entry in manifest["files"]:
        source = contained(backup_root, entry["path"])
        target = contained(stage, entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if checksum(target) != entry["sha256"]:
            raise ValueError("Restore copy verification failed; destination was not changed.")
    with closing(sqlite3.connect(stage / "porchlight.db")) as connection:
        sanitize(connection)
    from porchlight.storage.database import Database

    db = Database(stage)
    try:
        db.migrate()
        with db.engine.connect() as connection:
            if connection.exec_driver_sql("PRAGMA integrity_check").scalar() != "ok":
                raise ValueError("Restored database integrity failed.")
    finally:
        db.close()
    os.rename(stage, config.data_root)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["backup", "restore"])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "backup":
            result = backup(Config(), args.backup)
        elif args.destination:
            result = restore(args.backup, args.destination, apply=args.apply)
        else:
            raise ValueError("Supply a new restore destination.")
        print(json.dumps(result))
        return 0
    except (ValueError, RuntimeError) as error:
        print(json.dumps({"passed": False, "message": str(error)}))
    except Exception:
        print(
            json.dumps(
                {
                    "passed": False,
                    "message": "Local backup/restore could not complete. "
                    "No existing archive was replaced.",
                }
            )
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
