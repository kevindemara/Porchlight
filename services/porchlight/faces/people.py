"""Owner-named SFace templates in a current-Windows-user DPAPI envelope."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from porchlight.api.contracts import ApiError
from porchlight.faces.contracts import PersonProfile, PersonProfiles
from porchlight.faces.recognizer import cosine_score, normalized
from porchlight.security.vault import SecretStore, WindowsVault


def clean_name(value: str) -> str:
    name = " ".join(value.split())
    if not name or len(name) > 64 or any(ord(char) < 32 for char in name):
        raise ApiError(422, "FACE_NAME_INVALID", "Use a name of 1 to 64 printable characters.")
    return name


class People:
    def __init__(self, root: Path, vault: SecretStore | None = None):
        self.vault = vault or WindowsVault(root, "faces")
        self.lock = RLock()

    def _rows(self) -> list[dict[str, Any]]:
        value = self.vault.read() or {}
        rows = value.get("people", [])
        if not isinstance(rows, list):
            raise ApiError(503, "FACE_PROFILES_INVALID", "Local face profiles need repair.")
        return rows

    def list(self) -> PersonProfiles:
        with self.lock:
            return PersonProfiles(
                people=[
                    PersonProfile(
                        id=UUID(row["id"]),
                        name=row["name"],
                        created_at=row["created_at"],
                        samples=row.get("samples", 1),
                        manual_samples=row.get("manual_samples", row.get("samples", 1)),
                        automatic_samples=len(row.get("auto_sources", [])),
                    )
                    for row in self._rows()
                ]
            )

    def vectors(self) -> dict[str, tuple[tuple[float, ...], ...]]:
        with self.lock:
            return {
                row["id"]: tuple(
                    normalized(feature) for feature in row.get("features", [row["feature"]])
                )
                for row in self._rows()
            }

    def names(self) -> dict[str, str]:
        with self.lock:
            return {row["id"]: row["name"] for row in self._rows()}

    def manual_vectors(self) -> dict[str, tuple[tuple[float, ...], ...]]:
        with self.lock:
            result: dict[str, tuple[tuple[float, ...], ...]] = {}
            for row in self._rows():
                examples = row.get("features", [row["feature"]])
                sources = row.get("feature_sources", ["manual"] * len(examples))
                result[row["id"]] = tuple(
                    normalized(feature)
                    for feature, source in zip(examples, sources, strict=True)
                    if source == "manual"
                )
            return result

    def create(self, name: str, feature: tuple[float, ...]) -> PersonProfile:
        return self.create_samples(name, [feature])

    def create_samples(
        self, name: str, features: Sequence[tuple[float, ...]]
    ) -> PersonProfile:
        name = clean_name(name)
        if not 1 <= len(features) <= 32:
            raise ApiError(422, "FACE_SAMPLES_INVALID", "Choose 1 to 32 face samples.")
        vectors = [normalized(feature) for feature in features]
        with self.lock:
            rows = self._rows()
            if len(rows) >= 100:
                raise ApiError(409, "FACE_PROFILE_LIMIT", "Remove a person before adding another.")
            if any(row["name"].casefold() == name.casefold() for row in rows):
                raise ApiError(
                    409,
                    "FACE_NAME_EXISTS",
                    "This name already exists. Add this face to the saved person instead.",
                )
            profile = PersonProfile(
                id=uuid4(), name=name, created_at=datetime.now(UTC).isoformat(),
                samples=len(vectors), manual_samples=len(vectors),
            )
            rows.append({
                **profile.model_dump(mode="json"),
                "feature": list(normalized(tuple(
                    sum(vector[index] for vector in vectors) / len(vectors)
                    for index in range(len(vectors[0]))
                ))),
                "features": [list(vector) for vector in vectors],
                "feature_sources": ["manual"] * len(vectors),
                "manual_samples": len(vectors),
                "auto_sources": [],
            })
            self.vault.write({"people": rows})
            return profile

    def rename(self, identifier: UUID, name: str) -> PersonProfile:
        name = clean_name(name)
        with self.lock:
            rows = self._rows()
            row = next((item for item in rows if item["id"] == str(identifier)), None)
            if row is None:
                raise ApiError(404, "FACE_PERSON_NOT_FOUND", "This person is unavailable.")
            if any(item is not row and item["name"].casefold() == name.casefold() for item in rows):
                raise ApiError(409, "FACE_NAME_EXISTS", "This name already exists.")
            row["name"] = name
            self.vault.write({"people": rows})
            return PersonProfile(
                id=identifier,
                name=name,
                created_at=row["created_at"],
                samples=row.get("samples", 1),
                manual_samples=row.get("manual_samples", row.get("samples", 1)),
                automatic_samples=len(row.get("auto_sources", [])),
            )

    def add_sample(self, identifier: UUID, feature: tuple[float, ...]) -> PersonProfile:
        return self.add_samples(identifier, [feature])

    def add_samples(
        self, identifier: UUID, features: Sequence[tuple[float, ...]]
    ) -> PersonProfile:
        if not 1 <= len(features) <= 32:
            raise ApiError(422, "FACE_SAMPLES_INVALID", "Choose 1 to 32 face samples.")
        vectors = [normalized(feature) for feature in features]
        with self.lock:
            rows = self._rows()
            row = next((item for item in rows if item["id"] == str(identifier)), None)
            if row is None:
                raise ApiError(404, "FACE_PERSON_NOT_FOUND", "This person is unavailable.")
            count = int(row.get("samples", 1))
            if count + len(vectors) > 32:
                raise ApiError(409, "FACE_SAMPLE_LIMIT", "This person can have at most 32 samples.")
            previous = normalized(row["feature"])
            # Legacy profiles retain their existing average as the first exemplar.
            # New samples remain separate so a useful pose is not diluted by averaging.
            examples = row.get("features", [list(previous)])
            examples.extend(list(vector) for vector in vectors)
            row["features"] = examples
            sources = row.get("feature_sources", ["manual"] * (len(examples) - len(vectors)))
            sources.extend("manual" for _ in vectors)
            row["feature_sources"] = sources
            for vector in vectors:
                previous = normalized(tuple(
                    (count * old + new) / (count + 1)
                    for old, new in zip(previous, vector, strict=True)
                ))
                count += 1
            row["feature"] = list(previous)
            row["samples"] = count
            row["manual_samples"] = row.get(
                "manual_samples", count - len(vectors) - len(row.get("auto_sources", []))
            ) + len(vectors)
            self.vault.write({"people": rows})
            return PersonProfile(
                id=identifier,
                name=row["name"],
                created_at=row["created_at"],
                samples=count,
                manual_samples=row["manual_samples"],
                automatic_samples=len(row.get("auto_sources", [])),
            )

    def add_automatic_sample(
        self, identifier: UUID, feature: tuple[float, ...], source_event_id: str
    ) -> bool:
        """One local template per clip; automatic templates never become seed evidence."""
        vector = normalized(feature)
        with self.lock:
            rows = self._rows()
            row = next((item for item in rows if item["id"] == str(identifier)), None)
            if row is None:
                return False
            manual_count = int(row.get("manual_samples", row.get("samples", 1)))
            sources = row.get("auto_sources", [])
            examples = row.get("features", [row["feature"]])
            if (
                manual_count < 8 or int(row.get("samples", 1)) >= 32
                or source_event_id in sources
                or any(cosine_score(vector, old) >= 0.98 for old in examples)
            ):
                return False
            count = int(row.get("samples", 1))
            previous = normalized(row["feature"])
            row["feature"] = list(normalized(tuple(
                (count * old + new) / (count + 1)
                for old, new in zip(previous, vector, strict=True)
            )))
            row["features"] = [*examples, list(vector)]
            row["feature_sources"] = [
                *row.get("feature_sources", ["manual"] * len(examples)), "auto"
            ]
            row["auto_sources"] = [*sources, source_event_id]
            row["manual_samples"] = manual_count
            row["samples"] = count + 1
            self.vault.write({"people": rows})
            return True

    def delete(self, identifier: UUID) -> None:
        with self.lock:
            rows = self._rows()
            remaining = [row for row in rows if row["id"] != str(identifier)]
            if len(remaining) == len(rows):
                raise ApiError(404, "FACE_PERSON_NOT_FOUND", "This person is unavailable.")
            self.vault.write({"people": remaining})
