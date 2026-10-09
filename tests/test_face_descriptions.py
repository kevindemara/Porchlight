"""Synthetic identity metadata and display text; no camera imagery or real profiles."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from porchlight.faces.contracts import FaceBox, FaceFrame, FaceReport
from porchlight.faces.descriptions import FaceDescription, description_context, personalize_summary
from porchlight.storage.models import Analysis, Event, FaceDetection, Job

from tests.test_faces import store

ORIGINAL = "A person moves from left to right. A black car is visible. A white car is visible."


def evidence(profile_ids: list[str | None]) -> FaceReport:
    return FaceReport(
        frames=[
            FaceFrame(
                offset_ms=0,
                sha256="a" * 64,
                width=320,
                height=240,
                faces=[
                    FaceBox(
                        x=index * 60,
                        y=10,
                        width=50,
                        height=50,
                        score=0.95,
                        small=False,
                        low_sharpness=False,
                        profile_id=profile_id,
                        match_score=0.72,
                    )
                    for index, profile_id in enumerate(profile_ids)
                ],
            )
        ]
    )


@pytest.mark.parametrize(
    "case",
    [
        "unmatched",
        "two_profiles",
        "two_people",
        "two_faces",
        "deleted_profile",
        "no_analysis",
    ],
)
def test_ambiguous_and_unknown_people_keep_generic_description(case: str) -> None:
    first, second = str(uuid4()), str(uuid4())
    names = {first: "Alex", second: "Sam"}
    ids: list[str | None] = [first]
    person_count = 1
    if case == "unmatched":
        ids = [None]
    elif case == "two_profiles":
        ids = [first, second]
    elif case == "two_people":
        person_count = 2
    elif case == "two_faces":
        ids = [first, None]
    elif case == "deleted_profile":
        names = {}
    elif case == "no_analysis":
        person_count = 0
    context = description_context(evidence(ids), names, person_count)
    assert personalize_summary(ORIGINAL, context) == ORIGINAL


def test_names_are_literal_and_only_one_subject_is_replaced() -> None:
    name = r"Alex \g<0>"
    context = FaceDescription((name,), name)
    assert personalize_summary(ORIGINAL, context) == ORIGINAL.replace("A person", name, 1)
    assert personalize_summary("A car is visible next to a person.", context) == (
        "A car is visible next to a person."
    )
    ambiguous = "A person is visible. A person moves from left to right."
    assert personalize_summary(ambiguous, context) == ambiguous
    assert personalize_summary(None, context) is None


def test_sequential_people_are_not_treated_as_one_matched_person() -> None:
    first, second = str(uuid4()), str(uuid4())
    report = evidence([first])
    report.frames.append(evidence([second]).frames[0].model_copy(update={"offset_ms": 500}))
    context = description_context(report, {first: "Alex", second: "Sam"}, 1)
    assert context.names == ("Alex", "Sam")
    assert personalize_summary(ORIGINAL, context) == ORIGINAL


def test_activity_named_summary_preserves_ai_owner_edits_and_profile_lifecycle(
    authenticated, config
) -> None:
    client, headers = authenticated
    event_id = store(client.app.state.db, config, summary=ORIGINAL, analysis_status="analyzed")
    feature = tuple(1.0 if index == 0 else 0.0 for index in range(128))
    person = client.app.state.faces.people.create("Alex", feature)
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
                revision=1,
                model="synthetic",
                model_digest="synthetic",
                contract_digest="synthetic",
                input_fingerprint="synthetic",
                frames=[],
                elapsed_seconds=1,
                created_at=datetime.now(UTC).isoformat(),
                observation={"entities": [{"category": "person"}, {"category": "vehicle"}]},
            )
        )
        db.add(
            FaceDetection(
                event_id=event_id,
                job_id=str(uuid4()),
                report=evidence([str(person.id)]).model_dump(mode="json"),
                created_at=datetime.now(UTC).isoformat(),
                elapsed_seconds=0.1,
            )
        )
        db.commit()

    def description() -> dict:
        detail = client.get(f"/api/v1/events/{event_id}").json()
        listed = next(
            item for item in client.get("/api/v1/events").json()["items"] if item["id"] == event_id
        )
        assert detail["summary"] == listed["summary"]
        assert detail["ai_summary"] == ORIGINAL
        with client.app.state.db.session() as db:
            assert db.get(Event, event_id).summary == ORIGINAL
        return detail

    assert description()["summary"] == ORIGINAL.replace("A person", "Alex", 1)
    assert (
        client.patch(
            f"/api/v1/face-detection/people/{person.id}", headers=headers, json={"name": "Sam"}
        ).status_code
        == 200
    )
    assert description()["summary"] == ORIGINAL.replace("A person", "Sam", 1)
    assert (
        client.patch(
            f"/api/v1/events/{event_id}/annotation",
            headers=headers,
            json={
                "note": "",
                "favourite": False,
                "corrected_summary": "A person waits at the door.",
            },
        ).status_code
        == 200
    )
    assert description()["summary"] == "A person waits at the door."
    assert (
        client.patch(
            f"/api/v1/events/{event_id}/annotation",
            headers=headers,
            json={"note": "", "favourite": False, "corrected_summary": None},
        ).status_code
        == 200
    )
    assert description()["summary"] == ORIGINAL.replace("A person", "Sam", 1)
    with client.app.state.db.session() as db:
        event = db.get(Event, event_id)
        event.corrected_entities = []
        event.labels_summary = "No objects labelled by the owner."
        db.commit()
    assert description()["summary"] == "No objects labelled by the owner."
    with client.app.state.db.session() as db:
        event = db.get(Event, event_id)
        event.corrected_entities, event.labels_summary = None, None
        previous = db.query(Analysis).filter_by(event_id=event_id).one()
        next_job = Job(
            id=str(uuid4()),
            type="ai_analyze",
            dedup_key=str(uuid4()),
            payload={"event_id": event_id},
            status="done",
            attempt=1,
            available_at=0,
        )
        db.add(next_job)
        db.flush()
        db.add(
            Analysis(
                id=str(uuid4()),
                event_id=event_id,
                job_id=next_job.id,
                revision=2,
                model="synthetic",
                model_digest="synthetic",
                contract_digest="synthetic",
                input_fingerprint="synthetic",
                frames=[],
                elapsed_seconds=1,
                created_at=datetime.now(UTC).isoformat(),
                observation={"entities": [{"category": "person"}] * 2},
            )
        )
        assert len(previous.observation["entities"]) == 2
        db.commit()
    assert description()["summary"] == ORIGINAL
    assert (
        client.delete(f"/api/v1/face-detection/people/{person.id}", headers=headers).status_code
        == 204
    )
    assert description()["recognized_people"] == []
