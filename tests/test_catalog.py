from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from porchlight.api.contracts import CameraView
from porchlight.storage.models import Analysis, Event, FileDeletion, Job, MediaAsset, Tombstone
from sqlalchemy import select


def saved(client: TestClient, headers: dict[str, str], media: bytes) -> dict[str, str]:
    return dict(
        client.post(
            "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=media
        ).json()
    )


def test_local_delete_preserves_shared_asset_then_removes_bytes_and_history(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
) -> None:
    client, headers = authenticated
    original = saved(client, headers, synthetic_mp4)
    second = str(uuid4())
    with client.app.state.db.session() as db:
        db.add(
            Event(
                id=second,
                source_key="synthetic-cloud-delete",
                source_type="blink_cloud",
                media_id=original["media_id"],
                captured_at="2026-10-06T12:00:00+00:00",
                discovered_at="2026-10-06T12:00:00+00:00",
                timestamp_quality="upstream",
                analysis_status="not_analyzed",
            )
        )
        db.commit()
    assert client.delete(f"/api/v1/events/{second}").status_code == 403
    assert client.delete(f"/api/v1/events/{second}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/media/{original['media_id']}").content == synthetic_mp4
    with client.app.state.db.session() as db:
        assert db.get(Tombstone, "synthetic-cloud-delete") is not None
        asset = db.get(MediaAsset, original["media_id"])
        path = client.app.state.config.data_root / asset.relative_path
    assert client.delete(f"/api/v1/events/{original['id']}", headers=headers).status_code == 204
    assert not path.exists()
    assert client.get(f"/api/v1/media/{original['media_id']}").status_code == 404
    assert client.get("/api/v1/events").json()["items"] == []
    # Reimporting a local file is an explicit owner action and remains available.
    assert (
        client.post(
            "/api/v1/imports",
            headers={**headers, "Content-Type": "video/mp4"},
            content=synthetic_mp4,
        ).status_code
        == 201
    )


def test_deletion_journal_retries_without_touching_outside_or_reimported_media(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
    tmp_path: Path,
) -> None:
    client, headers = authenticated
    event = saved(client, headers, synthetic_mp4)
    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    with client.app.state.db.session() as db:
        asset = db.get(MediaAsset, event["media_id"])
        path = client.app.state.config.data_root / asset.relative_path
        db.add(FileDeletion(relative_path=asset.relative_path))
        db.add(FileDeletion(relative_path=str(outside)))
        db.commit()
    client.app.state.archive.recover_deletions()
    assert path.read_bytes() == synthetic_mp4
    assert outside.read_text() == "keep"


def test_description_correction_is_separate_searchable_and_clearable(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
) -> None:
    client, headers = authenticated
    event = saved(client, headers, synthetic_mp4)
    with client.app.state.db.session() as db:
        db.get(Event, event["id"]).summary = "Original AI description"
        db.commit()
    route = f"/api/v1/events/{event['id']}/annotation"
    edited = client.patch(
        route,
        headers=headers,
        json={"note": "", "favourite": True, "corrected_summary": "Owner reviewed wording"},
    ).json()
    assert edited["summary"] == "Owner reviewed wording"
    assert edited["ai_summary"] == "Original AI description"
    assert (
        client.get("/api/v1/events", params={"query": "reviewed"}).json()["items"][0]["id"]
        == event["id"]
    )
    # Older clients editing notes must not erase an existing correction.
    client.patch(route, headers=headers, json={"note": "note", "favourite": False})
    assert (
        client.get(f"/api/v1/events/{event['id']}").json()["corrected_summary"]
        == "Owner reviewed wording"
    )
    cleared = client.patch(
        route, headers=headers, json={"note": "", "favourite": False, "corrected_summary": None}
    ).json()
    assert cleared["summary"] == "Original AI description"


def test_entity_filters_use_latest_revision_and_same_entity(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
) -> None:
    client, headers = authenticated
    event = saved(client, headers, synthetic_mp4)
    with client.app.state.db.session() as db:
        for revision in (1, 2):
            job_id = str(uuid4())
            db.add(
                Job(
                    id=job_id,
                    type="ai_analyze",
                    dedup_key=job_id,
                    payload={"event_id": event["id"]},
                    status="done",
                    attempt=1,
                    available_at=0,
                )
            )
            db.flush()
            entities = [
                {
                    "category": "vehicle",
                    "color": "white" if revision == 1 else "black",
                    "direction": "stationary",
                },
                {"category": "package", "color": "white", "direction": "unknown"},
            ]
            db.add(
                Analysis(
                    id=str(uuid4()),
                    event_id=event["id"],
                    job_id=job_id,
                    revision=revision,
                    model="synthetic",
                    model_digest="synthetic",
                    contract_digest="synthetic",
                    input_fingerprint="synthetic",
                    frames=[],
                    observation={"entities": entities},
                    elapsed_seconds=1,
                    created_at="2026-10-06T12:00:00+00:00",
                )
            )
        db.commit()
    assert (
        len(
            client.get(
                "/api/v1/events",
                params={"category": "vehicle", "color": "black", "direction": "stationary"},
            ).json()["items"]
        )
        == 1
    )
    assert (
        client.get("/api/v1/events", params={"category": "vehicle", "color": "white"}).json()[
            "items"
        ]
        == []
    )
    assert (
        client.get("/api/v1/events", params={"category": "package", "color": "black"}).json()[
            "items"
        ]
        == []
    )
    assert client.delete(f"/api/v1/events/{event['id']}", headers=headers).status_code == 204
    with client.app.state.db.session() as db:
        assert not list(db.scalars(select(Analysis)))


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-10-07T00:00:00+00:00", "end": "2026-10-06T00:00:00+00:00"},
        {"start": "2026-10-06T00:00:00"},
        {"category": "DROP TABLE events"},
    ],
)
def test_filter_validation(
    authenticated: tuple[TestClient, dict[str, str]], params: dict[str, str]
) -> None:
    assert authenticated[0].get("/api/v1/events", params=params).status_code == 422


def test_camera_metadata_is_local_and_survives_inventory_refresh(
    authenticated: tuple[TestClient, dict[str, str]],
) -> None:
    client, headers = authenticated
    identifier = str(uuid4())
    camera = CameraView(
        id=identifier,
        name="Upstream name",
        family="doorbells",
        network_name="Synthetic",
        observed_armed=True,
    )
    client.app.state.blink.cameras = [camera]
    route = f"/api/v1/cameras/{identifier}/metadata"
    assert client.patch(route, json={"name": "Porch", "group": "Outside"}).status_code == 403
    edited = client.patch(route, headers=headers, json={"name": "Porch", "group": "Outside"})
    assert edited.json()["items"][0]["name"] == "Porch"
    assert client.app.state.blink.cameras[0].name == "Upstream name"
    client.app.state.blink.cameras = [camera.model_copy(update={"name": "Changed upstream"})]
    assert client.get("/api/v1/cameras").json()["items"][0]["group"] == "Outside"
