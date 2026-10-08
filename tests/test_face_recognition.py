"""Synthetic SFace wiring tests; these do not measure real-person accuracy."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from porchlight.config import Config
from porchlight.faces.contracts import FaceBox, FaceCandidate, FaceEnrollment
from porchlight.faces.detector import Detector
from porchlight.faces.gallery import GalleryItem, group_faces
from porchlight.faces.people import People
from porchlight.faces.recognizer import (
    Recognizer,
    best_match,
    check_recognizer,
    cosine_score,
    normalized,
)


class MemoryVault:
    def __init__(self) -> None:
        self.value: dict[str, object] | None = None

    def read(self) -> dict[str, object] | None:
        return deepcopy(self.value)

    def write(self, value: dict[str, object]) -> None:
        self.value = deepcopy(value)


def unit(index: int) -> tuple[float, ...]:
    return tuple(1.0 if position == index else 0.0 for position in range(128))


def test_profiles_are_local_renameable_and_removable(tmp_path: Path) -> None:
    vault = MemoryVault()
    people = People(tmp_path, vault)
    first = people.create("  Alex  ", unit(0))
    assert people.list().people[0].name == "Alex"
    assert people.vectors()[str(first.id)] == (unit(0),)
    assert people.rename(first.id, "Sam").name == "Sam"
    assert people.add_sample(first.id, unit(0)).samples == 2
    assert people.vectors()[str(first.id)] == (unit(0), unit(0))
    assert people.names()[str(first.id)] == "Sam"
    people.delete(first.id)
    assert people.list().people == []
    assert vault.value == {"people": []}


def test_match_requires_score_and_separation() -> None:
    profiles = {"first": (unit(0),), "second": (unit(1),)}
    assert best_match(unit(0), profiles) == ("first", 1.0)
    assert best_match(unit(2), profiles) is None
    assert (
        best_match(normalized(tuple(1.0 if i < 2 else 0.0 for i in range(128))), profiles) is None
    )
    assert cosine_score(unit(0), unit(1)) == 0.0
    assert best_match(unit(2), {"first": (unit(0), unit(2))}) == ("first", 1.0)
    with pytest.raises(ValueError):
        normalized((1.0,))
    with pytest.raises(ValueError):
        FaceEnrollment(event_id=uuid4(), offset_ms=0, face_index=0)


def test_legacy_eight_sample_profile_accepts_more_distinct_examples(tmp_path: Path) -> None:
    vault = MemoryVault()
    people = People(tmp_path, vault)
    person = people.create("Kevin", unit(0))
    assert vault.value is not None
    row = vault.value["people"][0]
    row.pop("features")
    row["samples"] = 8
    saved = people.add_sample(person.id, unit(1))
    assert saved.samples == 9
    assert people.vectors()[str(person.id)] == (unit(0), unit(1))
    for _ in range(23):
        saved = people.add_sample(person.id, unit(1))
    assert saved.samples == 32
    with pytest.raises(Exception, match="32 samples"):
        people.add_sample(person.id, unit(1))


def test_gallery_suggests_groups_without_declaring_identity() -> None:
    def face(event_id: str, offset: int, score: float = 0.9) -> FaceCandidate:
        return FaceCandidate(
            event_id=event_id,
            captured_at="2026-10-08T00:00:00Z",
            frame_sha256="a" * 64,
            offset_ms=offset,
            face_index=0,
            width=320,
            height=240,
            box=FaceBox(
                x=10, y=10, width=60, height=60, score=score,
                small=False, low_sharpness=False,
            ),
        )

    first, second = str(uuid4()), str(uuid4())
    groups = group_faces(
        [
            GalleryItem(face(first, 0), unit(0)),
            GalleryItem(face(second, 1000), unit(0)),
            GalleryItem(face(second, 2000), unit(1)),
        ],
        {},
        {},
    )
    assert len(groups) == 2
    assert groups[0].name is None and groups[0].sightings == 2
    assert len(groups[0].samples) == 2
    assert groups[1].sightings == 1


def test_gallery_keeps_adjacent_faces_together_without_a_recognition_vector() -> None:
    event_id = uuid4()

    def face(offset: int, x: int) -> FaceCandidate:
        return FaceCandidate(
            event_id=event_id,
            captured_at="2026-10-08T00:00:00Z",
            frame_sha256="a" * 64,
            offset_ms=offset,
            face_index=0,
            width=320,
            height=240,
            box=FaceBox(
                x=x, y=10, width=60, height=60, score=0.9,
                small=True, low_sharpness=False,
            ),
        )

    groups = group_faces([
        GalleryItem(face(500, 14), None),
        GalleryItem(face(0, 10), None),
        GalleryItem(face(250, 180), None),
    ], {}, {})
    assert len(groups) == 2
    assert sorted(group.sightings for group in groups) == [1, 2]


def test_gallery_suggests_a_close_name_without_assigning_it() -> None:
    person_id, event_id = str(uuid4()), uuid4()
    near = tuple([0.4, 0.916515138991168] + [0.0] * 126)
    face = FaceCandidate(
        event_id=event_id, captured_at="2026-10-08T00:00:00Z",
        frame_sha256="a" * 64,
        offset_ms=0, face_index=0, width=320, height=240,
        box=FaceBox(x=10, y=10, width=60, height=60, score=0.9,
                    small=False, low_sharpness=False),
    )
    groups = group_faces([GalleryItem(face, near)], {person_id: (unit(0),)},
                         {person_id: "Known person"})
    assert len(groups) == 1
    assert groups[0].person_id is None
    assert groups[0].suggested_person_id == UUID(person_id)
    assert groups[0].suggested_name == "Known person"


def test_native_sface_matches_a_synthetic_yunet_row(config: Config) -> None:
    if not config.face_model.is_file() or not config.sface_model.is_file():
        pytest.skip("Optional local face models are not installed")
    check_recognizer(config.sface_model)
    import cv2
    import numpy as np

    random = np.random.default_rng(8)
    image = random.integers(0, 255, (240, 320, 3), dtype=np.uint8)
    encoded = cv2.imencode(".jpg", image)[1].tobytes()
    decoded = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
    row = np.array(
        [80, 40, 100, 100, 110, 75, 155, 75, 132, 100, 115, 125, 150, 125, 0.99],
        dtype=np.float32,
    )
    feature = Recognizer(config.sface_model).extract(decoded, row)
    person_id = uuid4()
    detector = Detector(config.face_model, config.sface_model, {str(person_id): (feature,)})

    class SyntheticNative:
        def setInputSize(self, _: tuple[int, int]) -> None:
            pass

        def detect(self, _: object) -> tuple[None, object]:
            return None, np.array([row])

    detector.native = SyntheticNative()
    report = detector.detect(encoded, 0)
    assert len(report.faces) == 1
    assert report.faces[0].profile_id == person_id
    assert report.faces[0].match_score is not None
    assert report.faces[0].match_score > 0.99
    assert "feature" not in report.model_dump_json()


def test_profile_routes_require_authentication(client) -> None:
    assert client.get("/api/v1/face-detection/people").status_code == 401
    assert client.get("/api/v1/face-detection/candidates").status_code == 401


def test_profile_mutations_require_csrf(authenticated) -> None:
    owner, headers = authenticated
    assert owner.get("/api/v1/face-detection/people").status_code == 200
    assert owner.post("/api/v1/face-detection/people", json={}).status_code == 403
    assert (
        owner.delete(f"/api/v1/face-detection/people/{uuid4()}", headers=headers).status_code == 404
    )
