import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

from alembic import command
from alembic.config import Config as MigrationConfig
from fastapi.testclient import TestClient
from porchlight.api.contracts import ApiError
from porchlight.config import ROOT, Config
from porchlight.storage.database import Database
from porchlight.storage.models import NotificationOutbox, NotificationRule
from sqlalchemy import select
from test_notifications import rule


def test_rule_updates_and_deletion_require_reviewed_version(authenticated) -> None:
    client, headers = authenticated
    definition = {**rule(), "enabled": False}
    saved = client.post(
        "/api/v1/notification-rules", headers=headers, json={"definition": definition}
    ).json()
    assert saved["revision"] == 1
    route = f"/api/v1/notification-rules/{saved['id']}"
    changed = {**definition, "name": "Newer synthetic rule", "categories": ["person"]}
    body = {"definition": changed, "expected_revision": 1}
    assert client.put(route, json=body).status_code == 403
    assert client.put(route, headers=headers, json={"definition": changed}).status_code == 422
    assert client.delete(route, headers=headers).status_code == 422
    updated = client.put(route, headers=headers, json=body)
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    stale = client.put(route, headers=headers, json=body)
    assert stale.status_code == 409 and stale.json()["code"] == "RULE_CONFLICT"
    stale_delete = client.delete(f"{route}?expected_revision=1", headers=headers)
    assert stale_delete.status_code == 409 and stale_delete.json()["code"] == "RULE_CONFLICT"
    current = next(
        r for r in client.get("/api/v1/notification-rules").json() if r["id"] == saved["id"]
    )
    assert current["definition"] == changed and current["revision"] == 2
    assert client.delete(f"{route}?expected_revision=2", headers=headers).status_code == 204
    assert client.put(route, headers=headers, json=body).status_code == 404
    client.cookies.clear()
    assert client.put(route, headers=headers, json=body).status_code == 401


def test_simultaneous_rule_edits_have_one_winner_without_new_alerts(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, _ = authenticated
    service = client.app.state.notifications
    original = service.save_rule({**rule(), "enabled": False})

    def change(name: str) -> str:
        try:
            updated = service.save_rule(
                {**original.definition, "name": name}, original.id, original.revision
            )
            assert updated.revision == 2
            return "saved"
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(change, ["Synthetic phone", "Synthetic desktop"]))
    assert sorted(outcomes) == ["RULE_CONFLICT", "saved"]
    with client.app.state.db.session() as db:
        row = db.get(NotificationRule, original.id)
        assert row.revision == 2 and row.values["name"] in {"Synthetic phone", "Synthetic desktop"}
        assert db.scalar(select(NotificationOutbox.id)) is None


def test_upgrade_preserves_existing_rule_and_seeds_initial_revision(config: Config) -> None:
    db = Database(config.data_root)
    migration = MigrationConfig()
    migration.set_main_option(
        "script_location", str(ROOT / "services/porchlight/storage/migrations")
    )
    identifier = str(uuid4())
    definition = {**rule(), "enabled": False}
    try:
        with db.engine.begin() as connection:
            migration.attributes["connection"] = connection
            command.upgrade(migration, "0016")
            connection.exec_driver_sql(
                'INSERT INTO notification_rules(id,"values",created_at) VALUES(?,?,?)',
                (identifier, json.dumps(definition), datetime.now(UTC).isoformat()),
            )
        db.migrate()
        with db.session() as session:
            row = session.get(NotificationRule, identifier)
            assert row and row.revision == 1 and row.values == definition
    finally:
        db.close()
