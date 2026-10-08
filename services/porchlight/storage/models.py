from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Owner(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    login_name: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float)


class Session(Base):
    __tablename__ = "sessions"
    id_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    csrf_hash: Mapped[str] = mapped_column(String)
    expires_at: Mapped[float] = mapped_column(Float)


class SettingsRow(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    values: Mapped[dict[str, Any]] = mapped_column(JSON)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempted_at: Mapped[float] = mapped_column(Float, index=True)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String)
    source_key: Mapped[str] = mapped_column(String, unique=True)
    captured_at: Mapped[str | None] = mapped_column(String, nullable=True)
    discovered_at: Mapped[str] = mapped_column(String)
    timestamp_quality: Mapped[str] = mapped_column(String)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"))
    analysis_status: Mapped[str] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    favourite: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    camera_id: Mapped[str | None] = mapped_column(String, nullable=True)
    corrected_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_entities: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    labels_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_revision: Mapped[int] = mapped_column(Integer, default=0)
    correction_based_on: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correction_updated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    historical: Mapped[bool] = mapped_column(Boolean, default=False)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    sha256: Mapped[str] = mapped_column(String, unique=True)
    relative_path: Mapped[str] = mapped_column(String)
    bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float] = mapped_column(Float)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[Literal["video/mp4", "image/jpeg"]] = mapped_column(
        String, default="video/mp4"
    )


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    dedup_key: Mapped[str] = mapped_column(String, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String)
    attempt: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[float] = mapped_column(Float)
    lease_until: Mapped[float | None] = mapped_column(Float, nullable=True)
    safe_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class IntegrationState(Base):
    __tablename__ = "integration_state"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSON)


class RecordingScan(Base):
    __tablename__ = "recording_scans"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    since: Mapped[float] = mapped_column(Float)
    page: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    checked_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    history_days: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RecordingReference(Base):
    __tablename__ = "recording_references"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_key: Mapped[str] = mapped_column(String, unique=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("recording_scans.id"))
    source_type: Mapped[str] = mapped_column(String)
    camera_id: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_timestamp: Mapped[str] = mapped_column(String)
    discovered_at: Mapped[str] = mapped_column(String)
    # Only a validated relative REST path; signed queries and credential URLs are rejected.
    media_path: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    safe_error: Mapped[str | None] = mapped_column(String, nullable=True)
    historical: Mapped[bool] = mapped_column(Boolean, default=False)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("event_id", "revision"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True)
    revision: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String)
    model_digest: Mapped[str] = mapped_column(String)
    contract_digest: Mapped[str] = mapped_column(String)
    input_fingerprint: Mapped[str] = mapped_column(String)
    frames: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    observation: Mapped[dict[str, Any]] = mapped_column(JSON)
    elapsed_seconds: Mapped[float] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(String)


class Capture(Base):
    __tablename__ = "live_captures"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String)
    camera_name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    saved_at: Mapped[str] = mapped_column(String, index=True)
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    safe_error: Mapped[str | None] = mapped_column(String, nullable=True)
    favourite: Mapped[bool] = mapped_column(Boolean, default=False)


class Tombstone(Base):
    __tablename__ = "source_tombstones"
    source_key: Mapped[str] = mapped_column(String, primary_key=True)
    deleted_at: Mapped[str] = mapped_column(String)


class FileDeletion(Base):
    __tablename__ = "file_deletions"
    relative_path: Mapped[str] = mapped_column(String, primary_key=True)


class CameraMetadata(Base):
    __tablename__ = "camera_metadata"
    camera_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    group: Mapped[str] = mapped_column(String)


class NotificationRule(Base):
    __tablename__ = "notification_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class SavedView(Base):
    __tablename__ = "saved_views"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    rule_id: Mapped[str] = mapped_column(ForeignKey("notification_rules.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    dedup_key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String)
    available_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float)
    attempt: Mapped[int] = mapped_column(Integer)
    safe_error: Mapped[str | None] = mapped_column(String, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("notification_rules.id", ondelete="SET NULL"), nullable=True
    )
    tag: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class PushDevice(Base):
    __tablename__ = "push_devices"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    endpoint_hash: Mapped[str] = mapped_column(String, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String)


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("push_devices.id", ondelete="CASCADE"))
    outbox_id: Mapped[str | None] = mapped_column(
        ForeignKey("notification_outbox.id", ondelete="CASCADE"), nullable=True
    )
    dedup_key: Mapped[str] = mapped_column(String, unique=True)
    event_id: Mapped[str | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    tag: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    available_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    safe_error: Mapped[str | None] = mapped_column(String, nullable=True)


class CameraCommand(Base):
    __tablename__ = "camera_commands"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String)
    desired: Mapped[bool] = mapped_column(Boolean)
    state: Mapped[str] = mapped_column(String)
    observed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    safe_error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)


class FaceDetection(Base):
    __tablename__ = "face_detections"
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    job_id: Mapped[str] = mapped_column(String)
    report: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)
    elapsed_seconds: Mapped[float] = mapped_column(Float)
