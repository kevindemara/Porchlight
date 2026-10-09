"""Read-time names for a single-person description; stored AI text stays immutable."""

import re
from dataclasses import dataclass

from porchlight.faces.contracts import FaceReport

PERSON_SUBJECT = re.compile(r"(^|(?<=[.!?])\s+)(A person|The person)\b", re.IGNORECASE)


@dataclass(frozen=True)
class FaceDescription:
    names: tuple[str, ...] = ()
    single_person_name: str | None = None


def description_context(
    report: FaceReport, names: dict[str, str], person_count: int
) -> FaceDescription:
    matched_ids = {
        str(face.profile_id) for frame in report.frames for face in frame.faces if face.profile_id
    }
    resolved = tuple(sorted({names[key] for key in matched_ids if key in names}, key=str.casefold))
    single_name = None
    if (
        person_count == 1
        and len(matched_ids) == 1
        and len(resolved) == 1
        and all(len(frame.faces) <= 1 for frame in report.frames)
    ):
        single_name = resolved[0]
    return FaceDescription(resolved, single_name)


def personalize_summary(summary: str | None, context: FaceDescription) -> str | None:
    if not summary or not context.single_person_name:
        return summary
    subjects = list(PERSON_SUBJECT.finditer(summary))
    if len(subjects) != 1:
        return summary
    subject = subjects[0]
    # Slicing keeps owner names literal, including backslashes and punctuation.
    return summary[: subject.start(2)] + context.single_person_name + summary[subject.end(2) :]
