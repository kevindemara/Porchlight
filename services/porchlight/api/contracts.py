from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationInfo, field_validator


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        retryable: bool = False,
        retry_after: float | None = None,
    ):
        self.status, self.code, self.message, self.retryable = status, code, message, retryable
        self.retry_after = retry_after


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelayTrustRequired(ApiError):
    def __init__(self, fingerprint: str, pem: str):
        super().__init__(
            409, "LIVE_CERTIFICATE_REVIEW", "Blink’s live relay needs certificate review."
        )
        self.fingerprint, self.pem = fingerprint, pem


class Credentials(Contract):
    login_name: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: SecretStr = Field(min_length=1, max_length=128)


class Claim(Credentials):
    bootstrap_token: SecretStr = Field(min_length=1, max_length=128)


class SetupState(Contract):
    owner_created: bool


class PushKeys(Contract):
    p256dh: str = Field(min_length=80, max_length=100)
    auth: str = Field(min_length=20, max_length=30)


class PushPairRequest(Contract):
    name: str = Field(min_length=1, max_length=60)
    endpoint: str = Field(min_length=30, max_length=2048)
    keys: PushKeys


class PushDeviceView(Contract):
    id: str
    name: str
    enabled: bool
    created_at: str


class PushDeliveryView(Contract):
    id: str
    device_id: str
    event_id: str | None
    status: str
    created_at: str
    safe_error: str | None


class PushStatus(Contract):
    dependency_ready: bool
    configured: bool
    public_origin: str | None
    public_key: str | None
    message: str
    devices: list[PushDeviceView]
    deliveries: list[PushDeliveryView]
    paired_device_id: str | None = None


class BootstrapGrant(Contract):
    token: str
    expires_in_seconds: int


class SessionView(Contract):
    login_name: str
    csrf_token: str


class Component(Contract):
    state: Literal["ready", "not_configured", "unverified", "unavailable", "disabled"]
    message: str


class DiagnosticCheck(Contract):
    key: str
    label: str
    state: Literal["ready", "not_configured", "unverified", "unavailable", "disabled"]
    message: str
    last_success_at: str | None = None
    heartbeat_at: str | None = None
    safe_error: str | None = None
    action: str | None = None
    queued: int = 0
    running: int = 0
    needs_attention: int = 0


class Health(Contract):
    version: str
    database: Component
    archive: Component
    blink: Component
    ai: Component
    media_tools: Component
    notifications: Component
    live_view: Component
    free_space_bytes: int
    worker_heartbeat: str
    data_root: str
    camera_count: int
    event_count: int
    archive_bytes: int = 0
    reserve_bytes: int = 0
    archive_budget_bytes: int = 0
    recording_last_checked_at: str | None = None
    checks: list[DiagnosticCheck] = Field(default_factory=list)


class AppSettings(Contract):
    revision: int = Field(ge=1)
    timezone: str = "America/Toronto"
    ai_enabled: bool = False
    ai_model: str | None = None
    ai_workload: Literal["light", "balanced"] = "balanced"
    retention_days: int = Field(default=30, ge=1, le=3650)
    retention_enabled: bool = False
    archive_budget_gib: int = Field(default=50, ge=5, le=10000)
    reserve_gib: int = Field(default=5, ge=1, le=1000)
    theme: Literal["system", "light", "dark"] = "system"
    blink_entitlement: Literal["unknown", "paid", "trial", "none"] = "unknown"

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Choose a valid IANA timezone.") from exc
        return value

    @field_validator("ai_model")
    @classmethod
    def model_valid(cls, value: str | None) -> str | None:
        if value and (len(value) > 160 or not re.fullmatch(r"[a-zA-Z0-9_.:/-]+", value)):
            raise ValueError("Choose an installed model name.")
        return value


class ModelView(Contract):
    name: str
    digest: str
    size_bytes: int
    vision: bool
    local: bool
    reason: str


class AiResources(Contract):
    available: bool
    loaded_models: int
    other_loaded_models: int
    loaded_vram_bytes: int
    selected_loaded: bool
    inference_busy: bool
    contention_possible: bool


class ModelList(Contract):
    version: str
    models: list[ModelView]


class ModelTestRequest(Contract):
    model: str = Field(min_length=1, max_length=160)


class ModelTestResult(Contract):
    passed: bool
    model: str
    digest: str
    elapsed_seconds: float
    message: str


Category = Literal["person", "vehicle", "animal", "package", "other", "unknown"]
Color = Literal[
    "black",
    "white",
    "gray",
    "silver",
    "blue",
    "red",
    "green",
    "yellow",
    "orange",
    "brown",
    "beige",
    "other",
]
Direction = Literal[
    "left_to_right",
    "right_to_left",
    "toward_camera",
    "away_from_camera",
    "stationary",
    "unknown",
]


Action = Literal[
    "visible",
    "moving",
    "passing",
    "approaching",
    "departing",
    "stopping",
    "parked",
    "placing_object",
    "picking_up_object",
    "unknown",
]


class OwnerEntity(Contract):
    category: Category
    subtype: (
        Literal[
            "car",
            "truck",
            "van",
            "bus",
            "motorcycle",
            "bicycle",
            "dog",
            "cat",
            "bird",
            "box",
            "envelope",
        ]
        | None
    ) = None
    color: Color | None = None
    actions: list[Action] = Field(default=["visible"], min_length=1, max_length=6)
    direction: Direction = "unknown"

    @field_validator("actions")
    @classmethod
    def unique_actions(cls, value: list[Action]) -> list[Action]:
        if len(set(value)) != len(value):
            raise ValueError("Choose each action once.")
        return value

    @field_validator("subtype")
    @classmethod
    def matching_subtype(cls, value: str | None, info: ValidationInfo) -> str | None:
        allowed = {
            "vehicle": {"car", "truck", "van", "bus", "motorcycle", "bicycle"},
            "animal": {"dog", "cat", "bird"},
            "package": {"box", "envelope"},
        }
        if value and value not in allowed.get(str(info.data.get("category", "")), set()):
            raise ValueError("Choose a type within the selected category.")
        return value


class LabelCorrection(Contract):
    revision: int = Field(ge=0)
    based_on: int | None = Field(default=None, ge=1)
    entities: list[OwnerEntity] | None = Field(max_length=20)


class EventView(Contract):
    id: str
    source_type: str
    captured_at: str | None
    discovered_at: str
    timestamp_quality: str
    media_id: str
    analysis_status: str
    summary: str | None
    favourite: bool
    note: str
    duration_seconds: float
    camera_id: str | None = None
    corrected_summary: str | None = None
    ai_summary: str | None = None
    media_type: Literal["video/mp4", "image/jpeg"] = "video/mp4"
    historical: bool = False
    object_categories: list[str] = Field(default_factory=list)
    corrected_entities: list[OwnerEntity] | None = None
    correction_revision: int = 0
    correction_based_on: int | None = None
    correction_updated_at: str | None = None
    labels_source: Literal["ai", "owner", "none"] = "none"
    recognized_people: list[str] = Field(default_factory=list)


class EventList(Contract):
    items: list[EventView]
    next_cursor: str | None


class Annotation(Contract):
    favourite: bool
    note: str = Field(max_length=2000)
    corrected_summary: str | None = Field(default=None, max_length=500)


class EventFilters(Contract):
    cursor: str | None = Field(default=None, max_length=64)
    query: str = Field(default="", max_length=200)
    favourites: bool = False
    camera_id: str | None = Field(default=None, max_length=64)
    camera_ids: list[str] = Field(default_factory=list, max_length=32)
    categories: list[Category] = Field(default_factory=list, max_length=6)
    category: Category | None = None
    color: Color | None = None
    direction: Direction | None = None
    action: Action | None = None
    source: Literal["blink_cloud", "blink_local", "manual_import"] | None = None
    analysis: (
        Literal["not_analyzed", "queued", "analyzing", "analyzed", "analysis_failed"] | None
    ) = None
    start: datetime | None = None
    end: datetime | None = None
    daypart: Literal["all", "morning", "afternoon", "evening", "night"] = "all"

    @field_validator("start", "end")
    @classmethod
    def aware_time(cls, value: datetime | None) -> datetime | None:
        if value and value.tzinfo is None:
            raise ValueError("Use a timestamp with a timezone.")
        return value.astimezone(UTC) if value else None


class SavedViewRequest(Contract):
    name: str = Field(min_length=1, max_length=60)
    filters: EventFilters

    @field_validator("name")
    @classmethod
    def trimmed_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name this saved view.")
        return value.strip()


class SavedViewResult(SavedViewRequest):
    id: str
    created_at: str


class SearchRequest(Contract):
    query: str = Field(min_length=1, max_length=200)


class SearchPreview(Contract):
    filters: EventFilters
    needs_clarification: bool
    message: str
    timezone: str


class DigestHighlight(Contract):
    text: str
    event_id: str
    source: Literal["ai", "owner"] = "ai"


class DailyDigest(Contract):
    date: str
    timezone: str
    recording_count: int
    analyzed_count: int
    failed_count: int
    category_clip_counts: dict[str, int]
    highlights: list[DigestHighlight]
    coverage_note: str
    truncated: bool


class LocalCameraMetadata(Contract):
    name: str = Field(default="", max_length=120)
    group: str = Field(default="", max_length=80)


class RuleBody(Contract):
    definition: dict[str, object]


class RuleUpdate(RuleBody):
    expected_revision: int = Field(ge=1)


class RuleView(RuleBody):
    id: str
    created_at: str
    revision: int = Field(ge=1)


class InboxItem(Contract):
    id: str
    event_id: str | None
    title: str
    body: str
    created_at: str
    read: bool


class InboxView(Contract):
    items: list[InboxItem]
    unread: int
    next_cursor: str | None
    snoozed_until: str | None


class SnoozeRequest(Contract):
    minutes: int = Field(ge=0, le=1440)


class BlinkCredentials(Contract):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: SecretStr = Field(min_length=1, max_length=256)


class BlinkVerification(Contract):
    challenge_id: str = Field(min_length=1, max_length=64)
    code: SecretStr = Field(min_length=4, max_length=12)


class CameraRecording(Contract):
    summary: str | None = None
    summary_source: Literal["ai", "owner", "none"] = "none"
    analysis_status: str = "not_analyzed"
    source_type: Literal["blink_cloud", "blink_local"] = "blink_cloud"
    event_id: str
    media_id: str
    captured_at: str | None
    discovered_at: str


class CameraView(Contract):
    id: str
    name: str
    family: str
    network_name: str
    network_id: str | None = None
    observed_armed: bool | None
    recording_access: Literal["unverified", "cloud_archived", "local_archived"] = "unverified"
    live_view: Literal["disabled", "experimental"] = "disabled"
    latest_recording: CameraRecording | None = None
    group: str = ""
    observed_motion: bool | None = None
    observed_at: str | None = None
    network_control: bool = False
    motion_control: bool = False
    battery_state: str | None = None
    temperature_c: float | None = None


class CameraCommandRequest(Contract):
    request_id: str = Field(pattern=r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
    operation: Literal["network_armed", "motion_enabled"]
    desired: bool
    confirm_disable: bool = False


class CameraCommandView(Contract):
    id: str
    camera_id: str
    operation: Literal["network_armed", "motion_enabled"]
    desired: bool
    state: Literal["pending", "sending", "confirmed", "failed", "unknown"]
    observed: bool | None
    safe_error: str | None
    created_at: str


class CameraList(Contract):
    items: list[CameraView]


class CaptureView(Contract):
    id: str
    camera_id: str
    camera_name: str
    kind: Literal["recording", "snapshot"]
    state: Literal["recording", "saving", "ready", "failed"]
    saved_at: str
    bytes: int
    duration_seconds: float | None
    width: int
    height: int
    safe_error: str | None
    favourite: bool = False


class FavouriteRequest(Contract):
    favourite: bool


class RetentionRequest(Contract):
    days: int = Field(ge=1, le=3650)


class RetentionPreview(Contract):
    token: str
    days: int
    cutoff: str
    event_count: int
    capture_count: int
    reclaimable_bytes: int
    protected_count: int
    busy_count: int
    settings_revision: int
    expires_in_seconds: int = 300


class RetentionApply(Contract):
    token: str = Field(min_length=1, max_length=128)
    enable_automatic: bool = False


class RetentionResult(Contract):
    events_deleted: int
    captures_deleted: int
    automatic_enabled: bool


class CaptureList(Contract):
    items: list[CaptureView]
    next_cursor: str | None


class LiveSession(Contract):
    id: str
    camera_id: str
    state: Literal["starting", "receiving", "stalled", "ended", "failed"]
    message: str
    expires_at: str
    mime_type: str = 'video/mp4; codecs="avc1.42E01E"'
    bytes_received: int = 0
    media_age_seconds: float | None = None
    certificate_sha256: str | None = None
    recording: CaptureView | None = None


class BlinkStatus(Contract):
    state: Literal[
        "not_configured",
        "authenticating",
        "challenge_required",
        "connected",
        "reauth_required",
        "service_unavailable",
        "invalid_credentials",
        "vault_unavailable",
    ]
    message: str
    challenge_id: str | None = None
    challenge_expires_at: str | None = None
    inventory_checked_at: str | None = None
    camera_count: int = 0
    recording_access: Literal["unverified"] = "unverified"
    entitlement: Literal["unknown"] = "unknown"
    next_refresh_at: str | None = None


class RecordingHistory(Contract):
    state: Literal[
        "not_started", "queued", "scanning", "downloading", "paused", "complete", "needs_attention"
    ] = "not_started"
    days: Literal[0, 7, 30, 90, 365] | None = None
    discovered: int = 0
    archived: int = 0
    pending: int = 0
    failed: int = 0
    checked_at: str | None = None


class HistoryControl(Contract):
    action: Literal["start", "pause", "resume"]
    days: Literal[0, 7, 30, 90, 365] = 30


class RecordingSync(Contract):
    enabled: bool = False
    source: Literal["blink_cloud", "blink_local"] = "blink_cloud"
    discovered: int = 0
    archived: int = 0
    pending: int = 0
    failed: int = 0
    last_checked_at: str | None = None
    next_sync_at: str | None = None
    incomplete: bool = False
    state: Literal["not_started", "queued", "syncing", "ready", "needs_attention"] = "not_started"
    message: str = "Cloud recording discovery has not started."
    entitlement: Literal["unknown", "paid", "trial", "none"] = "unknown"
    entitlement_provenance: Literal["unknown", "owner_confirmed"] = "unknown"
    last_error_code: str | None = None
    no_plan_verified: Literal[False] = False
    history: RecordingHistory = Field(default_factory=RecordingHistory)


class RecordingControl(Contract):
    enabled: bool


class LocalModuleView(Contract):
    id: str
    name: str
    storage_ready: bool
    message: str
    checked_at: str


class LocalRecordingStatus(Contract):
    modules: list[LocalModuleView]
    sync: RecordingSync
    eligible: bool


class AnalysisStatus(Contract):
    enabled: bool
    ready: bool
    cloud_disabled: bool
    model: str | None
    message: str
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0


class AnalysisRequest(Contract):
    reanalyze: bool = False


class AnalysisJobView(Contract):
    job_id: str
    status: str


class AnalysisEntity(Contract):
    category: Category
    subtype: str | None
    color: Color | None
    actions: list[str]
    direction: Direction


class EvidenceFrame(Contract):
    frame_id: str
    offset_ms: int


class AnalysisView(Contract):
    revision: int
    model: str
    model_digest: str
    created_at: str
    elapsed_seconds: float
    frame_count: int
    workload: Literal["light", "balanced"] = "balanced"
    uncertainty: list[str]
    entities: list[AnalysisEntity] = Field(default_factory=list)
    sample_offsets_ms: list[int] = Field(default_factory=list)
    evidence_frames: list[EvidenceFrame] = Field(default_factory=list)
    scene_visibility: str | None = None
