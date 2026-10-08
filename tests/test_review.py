from uuid import uuid4

from fastapi.testclient import TestClient
from porchlight.storage.models import Analysis, Event, Job, Notification, NotificationOutbox
from sqlalchemy import func, select, text


def revision(client: TestClient, event_id: str, number: int) -> None:
    with client.app.state.db.session() as db:
        job = Job(
            id=str(uuid4()),
            type="ai_analyze",
            dedup_key=str(uuid4()),
            payload={"event_id": event_id},
            status="done",
            attempt=1,
            available_at=0,
        )
        db.add(job)
        db.flush()
        db.add(
            Analysis(
                id=str(uuid4()),
                event_id=event_id,
                job_id=job.id,
                revision=number,
                model="synthetic",
                model_digest="synthetic",
                contract_digest="synthetic",
                input_fingerprint="synthetic",
                frames=[],
                elapsed_seconds=1,
                created_at="2026-10-07T12:00:00Z",
                observation={
                    "entities": [
                        {
                            "category": "vehicle",
                            "subtype": "car",
                            "color": "white",
                            "actions": ["passing"],
                            "direction": "left_to_right",
                        }
                    ]
                },
            )
        )
        event = db.get(Event, event_id)
        event.summary, event.analysis_status = "AI original car", "analyzed"
        db.commit()


def test_structured_review_is_separate_effective_searchable_cas_and_silent(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
) -> None:
    client, headers = authenticated
    event = client.post(
        "/api/v1/imports",
        headers={**headers, "Content-Type": "video/mp4", "X-Recorded-At": "2026-10-07T12:00:00Z"},
        content=synthetic_mp4,
    ).json()
    revision(client, event["id"], 1)
    path = f"/api/v1/events/{event['id']}/labels"
    labels = [
        {
            "category": "animal",
            "subtype": "dog",
            "color": "brown",
            "actions": ["approaching"],
            "direction": "toward_camera",
        },
        {
            "category": "package",
            "subtype": "box",
            "color": "white",
            "actions": ["visible"],
            "direction": "stationary",
        },
    ]
    assert (
        client.put(path, json={"revision": 0, "based_on": 1, "entities": labels}).status_code == 403
    )
    response = client.put(
        path, headers=headers, json={"revision": 0, "based_on": 1, "entities": labels}
    )
    assert response.status_code == 200
    reviewed = response.json()
    assert reviewed["corrected_entities"] == labels
    assert reviewed["correction_revision"] == 1 and reviewed["correction_based_on"] == 1
    assert reviewed["labels_source"] == "owner" and reviewed["correction_updated_at"]
    assert reviewed["ai_summary"] == "AI original car" and "brown dog" in reviewed["summary"]
    assert reviewed["analysis_status"] == "analyzed"
    assert reviewed["object_categories"] == ["animal", "package"]
    assert (
        client.put(path, headers=headers, json={"revision": 0, "entities": []}).status_code == 409
    )
    for filters, match in (
        ({"category": "animal", "color": "brown", "action": "approaching"}, True),
        ({"category": "animal", "color": "white"}, False),
        ({"category": "animal", "action": "visible"}, False),
        ({"category": "vehicle"}, False),
        ({"query": "brown dog"}, True),
        ({"query": "do"}, True),
    ):
        items = client.get("/api/v1/events", params=filters).json()["items"]
        assert bool(items) is match
        assert (
            bool(client.get(f"/api/v1/events/{event['id']}/match", params=filters).json()) is match
        )
    digest = client.get("/api/v1/digests/daily", params={"day": "2026-10-07"}).json()
    assert digest["category_clip_counts"] == {"animal": 1, "package": 1}
    assert digest["highlights"][0]["source"] == "owner"
    revision(client, event["id"], 2)
    assert client.get(f"/api/v1/events/{event['id']}").json()["correction_based_on"] == 1
    assert (
        client.put(
            path, headers=headers, json={"revision": 1, "based_on": 99, "entities": labels}
        ).status_code
        == 422
    )
    assert client.get(f"/api/v1/events/{event['id']}").json()["corrected_entities"] == labels
    # Note clients and reanalysis cannot silently reset the owner's labels.
    assert (
        client.patch(
            f"/api/v1/events/{event['id']}/annotation",
            headers=headers,
            json={"note": "reviewed", "favourite": True},
        ).status_code
        == 200
    )
    empty = client.put(path, headers=headers, json={"revision": 1, "entities": []}).json()
    assert empty["corrected_entities"] == [] and empty["object_categories"] == []
    assert not client.get("/api/v1/events", params={"category": "vehicle"}).json()["items"]
    restored = client.put(path, headers=headers, json={"revision": 2, "entities": None}).json()
    assert restored["labels_source"] == "ai" and restored["corrected_entities"] is None
    assert restored["summary"] == "AI original car" and restored["object_categories"] == ["vehicle"]
    assert not client.get("/api/v1/events", params={"query": "brown dog"}).json()["items"]
    with client.app.state.db.session() as db:
        assert db.scalar(select(func.count()).select_from(Analysis)) == 2
        assert db.scalar(select(func.count()).select_from(Notification)) == 0
        assert db.scalar(select(func.count()).select_from(NotificationOutbox)) == 0
        db.execute(
            text("INSERT INTO event_search(event_search, rank) VALUES('integrity-check', 1)")
        )
    assert client.delete(f"/api/v1/events/{event['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/events/{event['id']}/match").json() is None
    client.cookies.clear()
    assert client.get(f"/api/v1/events/{event['id']}/match").status_code == 401
    assert (
        client.put(path, headers=headers, json={"revision": 3, "entities": []}).status_code == 401
    )


def test_owner_label_contract_bounds_and_does_not_claim_inference(
    authenticated: tuple[TestClient, dict[str, str]],
    synthetic_mp4: bytes,
) -> None:
    client, headers = authenticated
    event = client.post(
        "/api/v1/imports", headers={**headers, "Content-Type": "video/mp4"}, content=synthetic_mp4
    ).json()
    path = f"/api/v1/events/{event['id']}/labels"
    for entities in (
        [{"category": "face"}],
        [{"category": "person", "subtype": "dog"}],
        [{"category": "vehicle", "actions": ["identity"]}],
        [{"category": "vehicle", "actions": ["visible", "visible"]}],
        [{"category": "unknown", "actions": []}],
        [{"category": "unknown"}] * 21,
        [{"category": "unknown", "evidence_frame_ids": ["fake"]}],
    ):
        assert (
            client.put(
                path, headers=headers, json={"revision": 0, "entities": entities}
            ).status_code
            == 422
        )
    reviewed = client.put(
        path,
        headers=headers,
        json={"revision": 0, "entities": [{"category": "package", "subtype": "box"}]},
    ).json()
    assert reviewed["analysis_status"] == "not_analyzed" and reviewed["ai_summary"] is None
    assert reviewed["correction_based_on"] is None and reviewed["labels_source"] == "owner"
