"""Tentative local grouping for owner review; no face images or vectors are persisted."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from porchlight.faces.contracts import FaceCandidate, FaceGroup, FaceSuggestion
from porchlight.faces.recognizer import best_match, cosine_score, rank_profiles

GROUP_THRESHOLD = 0.55
GROUP_MARGIN = 0.07


@dataclass(frozen=True)
class GalleryItem:
    face: FaceCandidate
    feature: tuple[float, ...] | None


def suggest_face(
    item: GalleryItem,
    profiles: Mapping[str, Sequence[Sequence[float]]],
    names: Mapping[str, str],
) -> FaceSuggestion | None:
    """Offer a review-only name for an unlabeled face; never assign it here."""
    if item.face.box.profile_id is not None or item.feature is None:
        return None
    scores = rank_profiles(item.feature, profiles)
    if not scores or scores[0][0] not in names or scores[0][1] < 0.38:
        return None
    if len(scores) > 1 and scores[0][1] - scores[1][1] < 0.05:
        return None
    identifier = scores[0][0]
    return FaceSuggestion(face=item.face, person_id=UUID(identifier), name=names[identifier])


@dataclass
class _Group:
    id: str
    person_id: str | None
    name: str | None
    items: list[GalleryItem] = field(default_factory=list)


def _key(face: FaceCandidate) -> str:
    token = f"{face.event_id}:{face.offset_ms}:{face.face_index}".encode()
    return "unknown-" + hashlib.sha256(token).hexdigest()[:16]


def _quality(item: GalleryItem) -> tuple[int, int, float]:
    box = item.face.box
    return (
        int(not box.small and not box.low_sharpness),
        min(box.width, box.height),
        box.score,
    )


def _same_track(first: GalleryItem, second: GalleryItem) -> bool:
    """Conservatively join a moving face in nearby frames of one recording."""
    if first.feature is not None and second.feature is not None:
        if cosine_score(first.feature, second.feature) < 0.3:
            return False
    a_face, b_face = first.face, second.face
    if (
        a_face.event_id != b_face.event_id
        or not 0 < abs(a_face.offset_ms - b_face.offset_ms) <= 1000
        or a_face.width != b_face.width
        or a_face.height != b_face.height
    ):
        return False
    a, b = a_face.box, b_face.box
    intersection = max(0, min(a.x + a.width, b.x + b.width) - max(a.x, b.x)) * max(
        0, min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
    )
    union = a.width * a.height + b.width * b.height - intersection
    return union > 0 and intersection / union >= 0.35


def _suggest(
    group: _Group,
    profiles: Mapping[str, Sequence[Sequence[float]]],
    names: Mapping[str, str],
) -> str | None:
    if group.person_id:
        return None
    suggestions: set[str] = set()
    for item in group.items:
        if item.feature is None or item.face.box.small or item.face.box.low_sharpness:
            continue
        scores = rank_profiles(item.feature, profiles)
        if scores and scores[0][0] in names and scores[0][1] >= 0.38 and (
            len(scores) == 1 or scores[0][1] - scores[1][1] >= 0.05
        ):
            suggestions.add(scores[0][0])
    return next(iter(suggestions)) if len(suggestions) == 1 else None


def group_faces(
    items: list[GalleryItem],
    profiles: Mapping[str, Sequence[Sequence[float]]],
    names: Mapping[str, str],
) -> list[FaceGroup]:
    groups: list[_Group] = []
    for item in items:
        face, feature = item.face, item.feature
        person_id = str(face.box.profile_id) if face.box.profile_id else None
        if person_id not in names:
            person_id = None
        if person_id is None and feature is not None:
            match = best_match(feature, profiles)
            person_id = match[0] if match else None
        if person_id:
            group = next((row for row in groups if row.person_id == person_id), None)
            if group is None:
                group = _Group(person_id, person_id, names[person_id])
                groups.append(group)
        else:
            group = next(
                (
                    row for row in groups
                    if row.person_id is None
                    and any(_same_track(item, previous) for previous in row.items)
                ),
                None,
            )
            if (
                group is None and feature is not None
                and not face.box.small and not face.box.low_sharpness
            ):
                scores = sorted(
                    (
                        (
                            max(cosine_score(feature, previous.feature) for previous in row.items
                                if previous.feature is not None),
                            row,
                        )
                        for row in groups
                        if row.person_id is None
                        and any(previous.feature is not None for previous in row.items)
                        and not any(
                            previous.face.event_id == face.event_id
                            and previous.face.offset_ms == face.offset_ms
                            for previous in row.items
                        )
                    ),
                    key=lambda result: result[0],
                    reverse=True,
                )
                if scores and scores[0][0] >= GROUP_THRESHOLD and (
                    len(scores) == 1 or scores[0][0] - scores[1][0] >= GROUP_MARGIN
                ):
                    group = scores[0][1]
            if group is None:
                group = _Group(_key(face), None, None)
                groups.append(group)
        group.items.append(item)
    result: list[FaceGroup] = []
    for group in groups:
        suggestion = _suggest(group, profiles, names)
        result.append(FaceGroup(
            id=group.id,
            person_id=UUID(group.person_id) if group.person_id else None,
            name=group.name,
            suggested_person_id=UUID(suggestion) if suggestion else None,
            suggested_name=names[suggestion] if suggestion else None,
            sightings=len(group.items),
            samples=[item.face for item in sorted(group.items, key=_quality, reverse=True)[:3]],
        ))
    return result
