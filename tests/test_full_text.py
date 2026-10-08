from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config as MigrationConfig
from fastapi.testclient import TestClient
from porchlight.api.contracts import EventFilters
from porchlight.catalog import event_query
from porchlight.storage.database import Database
from porchlight.storage.models import Event, MediaAsset


def test_index_is_literal_unicode_transactional_and_deletion_safe(
    authenticated: tuple[TestClient, dict[str, str]], synthetic_mp4: bytes
) -> None:
    client, headers = authenticated
    event = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    ).json()
    route = f"/api/v1/events/{event['id']}/annotation"
    note = 'Literal 100% café a_b "quoted" OR vehicle C:\\door'
    assert (
        client.patch(route, headers=headers, json={"note": note, "favourite": False}).status_code
        == 200
    )
    for query in ("100%", "AFÉ", "a_b", '"quoted" OR', "C:\\door", "teral", "%", "_"):
        result = client.get("/api/v1/events", params={"query": query})
        assert result.status_code == 200, result.text
        assert [item["id"] for item in result.json()["items"]] == [event["id"]], query
    for query in ("100*", "vehicle OR nonexistent", "note:vehicle", '" OR 1=1 --'):
        assert client.get("/api/v1/events", params={"query": query}).json()["items"] == []
    assert client.get("/api/v1/events", params={"query": "bad\x00text"}).status_code == 422
    assert (
        client.patch(
            route, headers=headers, json={"note": "New text", "favourite": False}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/events", params={"query": "100%"}).json()["items"] == []
    with client.app.state.db.session() as session:
        saved = session.get(Event, event["id"])
        saved.summary = "Synthetic analyzer update"
        session.commit()
        saved.note = "Rolled back edit"
        session.flush()
        session.rollback()
    assert (
        client.get("/api/v1/events", params={"query": "analyzer"}).json()["items"][0]["id"]
        == event["id"]
    )
    assert client.get("/api/v1/events", params={"query": "Rolled back"}).json()["items"] == []
    assert client.delete(f"/api/v1/events/{event['id']}", headers=headers).status_code == 204
    assert client.get("/api/v1/events", params={"query": "analyzer"}).json()["items"] == []
    with client.app.state.db.engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO event_search(event_search, rank) VALUES('integrity-check', 1)"
        )


def test_search_migration_indexes_existing_records(tmp_path: Path) -> None:
    db = Database(tmp_path / "profile")
    configuration = MigrationConfig()
    configuration.set_main_option(
        "script_location", str(Path(__file__).parents[1] / "services/porchlight/storage/migrations")
    )
    try:
        with db.engine.begin() as connection:
            configuration.attributes["connection"] = connection
            command.upgrade(configuration, "0010")
        asset_id, event_id = str(uuid4()), str(uuid4())
        with db.session() as session:
            session.add(
                MediaAsset(
                    id=asset_id,
                    sha256="synthetic",
                    relative_path="media/synthetic.mp4",
                    bytes=1,
                    duration_seconds=1,
                    width=1,
                    height=1,
                )
            )
            session.flush()
            # Populate the actual old schema, without new ORM columns absent from revision 0010.
            session.connection().exec_driver_sql(
                "INSERT INTO events(id,source_type,source_key,discovered_at,timestamp_quality,"
                "media_id,analysis_status,favourite,note) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    "manual_import",
                    "old-synthetic",
                    "2026-10-07T00:00:00+00:00",
                    "unknown",
                    asset_id,
                    "not_analyzed",
                    0,
                    "Existing archive note",
                ),
            )
            session.commit()
        db.migrate()
        with db.session() as session:
            assert session.get(Event, event_id).historical is False
            assert (
                session.execute(event_query(EventFilters(query="archive"))).scalar_one().id
                == event_id
            )
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO event_search(event_search, rank) VALUES('integrity-check', 1)"
            )
    finally:
        db.close()
