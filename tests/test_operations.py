import json
import sqlite3
from pathlib import Path

import pytest
from conftest import ORIGIN, claim
from fastapi.testclient import TestClient
from porchlight.app import create_app
from porchlight.config import Config
from porchlight.operations import backup, restore, verify
from porchlight.storage.models import IntegrationState


def make_backup(config: Config, tmp_path: Path, synthetic_mp4: bytes) -> tuple[Path, str]:
    with TestClient(create_app(config), base_url=ORIGIN, client=("127.0.0.1", 42000)) as client:
        token = claim(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": token}
        event = client.post(
            "/api/v1/imports",
            headers={**headers, "Content-Type": "video/mp4"},
            content=synthetic_mp4,
        ).json()
        client.patch(
            f"/api/v1/events/{event['id']}/annotation",
            headers=headers,
            json={
                "favourite": True,
                "note": "synthetic backup note",
                "corrected_summary": "Reviewed synthetic clip",
            },
        )
        assert (
            client.put(
                f"/api/v1/events/{event['id']}/labels",
                headers=headers,
                json={"revision": 0, "entities": [{"category": "animal", "subtype": "dog"}]},
            ).status_code
            == 200
        )
        with client.app.state.db.session() as db:
            db.add(
                IntegrationState(
                    id="face_detection",
                    values={"enabled": True, "enabled_at": "2026-10-07T00:00:00Z"},
                )
            )
            db.add(IntegrationState(id="blink_live_certificates", values={"synthetic": "pin"}))
            db.add(
                IntegrationState(
                    id="local_manifest:synthetic:module", values={"request_id": "synthetic-pending"}
                )
            )
            db.commit()
        # A stopped-profile backup is required, rather than copying a live WAL file.
        with pytest.raises(RuntimeError):
            backup(config, tmp_path / "busy-backup")
    (config.data_root / "secrets").mkdir(exist_ok=True)
    (config.data_root / "secrets/blink.dpapi").write_bytes(b"synthetic encrypted secret excluded")
    destination = tmp_path / "complete-backup"
    result = backup(config, destination)
    assert result["passed"] and result["file_count"] == 2
    assert not (destination / "secrets").exists()
    return destination, event["media_id"]


def test_backup_restore_restarts_and_plays_original_without_sessions(
    config: Config,
    tmp_path: Path,
    synthetic_mp4: bytes,
) -> None:
    source, media_id = make_backup(config, tmp_path, synthetic_mp4)
    clone = tmp_path / "restored-profile"
    preview = restore(source, clone)
    assert preview["passed"] and not preview["applied"] and not clone.exists()
    assert restore(source, clone, apply=True)["applied"]
    with sqlite3.connect(clone / "porchlight.db") as db:
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
        assert (
            db.execute(
                "SELECT COUNT(*) FROM integration_state WHERE id='blink_live_certificates'"
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute(
                "SELECT COUNT(*) FROM integration_state WHERE id LIKE 'local_manifest:%'"
            ).fetchone()[0]
            == 0
        )
    with TestClient(
        create_app(Config(data_root=clone)), base_url=ORIGIN, client=("127.0.0.1", 42000)
    ) as client:
        assert client.get(f"/api/v1/media/{media_id}").status_code == 401
        login = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"login_name": "synthetic_owner", "password": "synthetic-test-passphrase"},
        )
        assert login.status_code == 200
        assert client.get(f"/api/v1/media/{media_id}").content == synthetic_mp4
        event = client.get("/api/v1/events").json()["items"][0]
        assert event["favourite"] and event["note"] == "synthetic backup note"
        assert event["corrected_summary"] == "Reviewed synthetic clip"
        assert event["corrected_entities"][0]["subtype"] == "dog"
        assert event["correction_revision"] == 1 and event["labels_source"] == "owner"
        assert (
            client.get("/api/v1/events", params={"category": "animal"}).json()["items"][0]["id"]
            == event["id"]
        )
        assert not client.get("/api/v1/settings").json()["ai_enabled"]
        assert not client.get("/api/v1/face-detection/status").json()["enabled"]
        assert client.get("/api/v1/integrations/blink/status").json()["state"] == "not_configured"
    with pytest.raises(ValueError, match="new destination"):
        restore(source, clone, apply=True)


def test_backup_verification_rejects_corruption_and_traversal(
    config: Config,
    tmp_path: Path,
    synthetic_mp4: bytes,
) -> None:
    source, _ = make_backup(config, tmp_path, synthetic_mp4)
    manifest = json.loads((source / "manifest.json").read_text())
    media = source / manifest["files"][1]["path"]
    media.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        verify(source)
    assert not (tmp_path / "not-restored").exists()
    manifest["files"][1]["path"] = "../outside"
    (source / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsafe path"):
        restore(source, tmp_path / "not-restored", apply=True)
