from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from porchlight.api.contracts import Contract


class FaceBox(Contract):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1, le=960)
    height: int = Field(ge=1, le=960)
    score: float = Field(ge=0.8, le=1, allow_inf_nan=False)
    small: bool
    low_sharpness: bool
    profile_id: UUID | None = None
    match_score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class FaceFrame(Contract):
    offset_ms: int = Field(ge=0, le=300000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    width: int = Field(ge=1, le=960)
    height: int = Field(ge=1, le=960)
    faces: list[FaceBox] = Field(max_length=25)

    @model_validator(mode="after")
    def contained(self) -> "FaceFrame":
        if any(f.x + f.width > self.width or f.y + f.height > self.height for f in self.faces):
            raise ValueError("Face rectangles must stay within their evidence frame.")
        return self


class FaceReport(Contract):
    policy: Literal["yunet-sampled-v1", "yunet-sampled-v2", "yunet-sampled-v3"] = (
        "yunet-sampled-v3"
    )
    model_sha256: str = Field(
        default="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        pattern=r"^[0-9a-f]{64}$",
    )
    recognition_model_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    frames: list[FaceFrame] = Field(min_length=1, max_length=48)

    @model_validator(mode="after")
    def ordered(self) -> "FaceReport":
        offsets = [f.offset_ms for f in self.frames]
        if offsets != sorted(set(offsets)):
            raise ValueError("Evidence timestamps must be unique and ordered.")
        return self


type FaceState = Literal["not_requested", "queued", "running", "done", "failed", "expired"]


class FaceResult(Contract):
    status: FaceState
    report: FaceReport | None = None
    created_at: str | None = None
    elapsed_seconds: float | None = None
    message: str | None = None
    people: dict[str, str] = Field(default_factory=dict)


class FaceStatus(Contract):
    ready: bool
    enabled: bool
    message: str
    queued: int
    running: int
    completed: int
    failed: int
    recognition_ready: bool = False
    people_count: int = 0
    auto_enroll_enabled: bool = False


class FaceControl(Contract):
    enabled: bool


class PersonProfile(Contract):
    id: UUID
    name: str = Field(min_length=1, max_length=64)
    created_at: str
    samples: int = Field(default=1, ge=1, le=32)
    manual_samples: int = Field(default=1, ge=0, le=32)
    automatic_samples: int = Field(default=0, ge=0, le=32)


class PersonProfiles(Contract):
    people: list[PersonProfile]


class FaceEnrollment(Contract):
    event_id: UUID
    offset_ms: int = Field(ge=0, le=300000)
    face_index: int = Field(ge=0, le=24)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    person_id: UUID | None = None

    @model_validator(mode="after")
    def one_target(self) -> "FaceEnrollment":
        if (self.name is None) == (self.person_id is None):
            raise ValueError("Choose a new name or one saved person.")
        return self


class FaceSelection(Contract):
    event_id: UUID
    offset_ms: int = Field(ge=0, le=300000)
    face_index: int = Field(ge=0, le=24)


class FaceEnrollmentBatch(Contract):
    samples: list[FaceSelection] = Field(min_length=1, max_length=12)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    person_id: UUID | None = None

    @model_validator(mode="after")
    def valid_batch(self) -> "FaceEnrollmentBatch":
        if (self.name is None) == (self.person_id is None):
            raise ValueError("Choose a new name or one saved person.")
        keys = {(item.event_id, item.offset_ms, item.face_index) for item in self.samples}
        if len(keys) != len(self.samples):
            raise ValueError("Select each face only once.")
        return self


class PersonRename(Contract):
    name: str = Field(min_length=1, max_length=64)


class FaceCandidate(Contract):
    event_id: UUID
    captured_at: str
    frame_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    offset_ms: int
    face_index: int
    width: int = Field(ge=1, le=960)
    height: int = Field(ge=1, le=960)
    box: FaceBox


class FaceSuggestion(Contract):
    face: FaceCandidate
    person_id: UUID
    name: str


class FaceCandidates(Contract):
    faces: list[FaceCandidate]


class FaceGroup(Contract):
    id: str
    person_id: UUID | None = None
    name: str | None = None
    suggested_person_id: UUID | None = None
    suggested_name: str | None = None
    sightings: int = Field(ge=1)
    samples: list[FaceCandidate] = Field(min_length=1, max_length=3)


class SavedFacePerson(Contract):
    person_id: UUID
    name: str
    samples: list[FaceCandidate] = Field(default_factory=list, max_length=3)


class FaceGallery(Contract):
    groups: list[FaceGroup]
    saved_people: list[SavedFacePerson] = Field(default_factory=list)
    suggestions: list[FaceSuggestion] = Field(default_factory=list)
    labeled_totals: dict[str, int] = Field(default_factory=dict)
    confirmed_totals: dict[str, int] = Field(default_factory=dict)
    recordings_reviewed: int = Field(ge=0)
    total_recordings: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    omitted_faces: int = Field(ge=0)


class FaceApprovalSelection(Contract):
    event_id: UUID
    offset_ms: int = Field(ge=0, le=300000)
    face_index: int = Field(ge=0, le=24)
    frame_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    box: FaceBox


class FaceApproval(Contract):
    person_id: UUID
    faces: list[FaceApprovalSelection] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def unique_faces(self) -> "FaceApproval":
        keys = {(face.event_id, face.offset_ms, face.face_index) for face in self.faces}
        if len(keys) != len(self.faces):
            raise ValueError("Select each face only once.")
        return self


class FaceApprovalResult(Contract):
    labeled: int = Field(ge=0)
    total_labeled: int = Field(ge=0)
    total_confirmed: int = Field(ge=0)


class FaceRescan(Contract):
    requested: int = Field(ge=0, le=20)
    queued: int = Field(ge=0, le=20)
    already_running: int = Field(ge=0, le=20)
