from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import FastAPI, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import func, select, text
from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.staticfiles import StaticFiles

from porchlight import __version__
from porchlight.activity import capture_event, timeline_rows
from porchlight.ai.evidence import Evidence
from porchlight.ai.ollama import Ollama
from porchlight.ai.pipeline import AnalysisPipeline
from porchlight.ai.readiness import inspect_machine
from porchlight.api.contracts import (
    AiReadiness,
    AiResources,
    AnalysisJobView,
    AnalysisRequest,
    AnalysisStatus,
    AnalysisView,
    Annotation,
    ApiError,
    AppSettings,
    BlinkCredentials,
    BlinkStatus,
    BlinkVerification,
    BootstrapGrant,
    CameraCommandRequest,
    CameraCommandView,
    CameraList,
    CameraRecording,
    CaptureList,
    CaptureView,
    Claim,
    Component,
    Credentials,
    DailyDigest,
    EventFilters,
    EventList,
    EventView,
    FavouriteRequest,
    Health,
    HistoryControl,
    InboxView,
    LabelCorrection,
    LiveSession,
    LocalCameraMetadata,
    LocalRecordingStatus,
    ModelList,
    ModelTestRequest,
    ModelTestResult,
    OwnerEntity,
    PushPairRequest,
    PushReceipt,
    PushStatus,
    RecordingControl,
    RecordingSync,
    RetentionApply,
    RetentionPreview,
    RetentionRequest,
    RetentionResult,
    RuleBody,
    RuleUpdate,
    RuleView,
    SavedViewRequest,
    SavedViewResult,
    SearchPreview,
    SearchRequest,
    SessionView,
    SetupState,
    SnoozeRequest,
)
from porchlight.catalog import Archive, event_query
from porchlight.changes import StateChanges
from porchlight.config import Config
from porchlight.controls import CameraControls
from porchlight.diagnostics import support_report
from porchlight.faces.contracts import (
    FaceApproval,
    FaceApprovalResult,
    FaceCandidates,
    FaceControl,
    FaceEnrollment,
    FaceEnrollmentBatch,
    FaceGallery,
    FaceRescan,
    FaceResult,
    FaceStatus,
    PersonProfile,
    PersonProfiles,
    PersonRename,
)
from porchlight.faces.descriptions import FaceDescription, personalize_summary
from porchlight.faces.pipeline import FacePipeline
from porchlight.healthchecks import checks as independent_checks
from porchlight.ingestion.imports import Importer
from porchlight.ingestion.recordings import Recordings
from porchlight.ingestion.thumbnails import Thumbnails
from porchlight.library import MAX_SNAPSHOT, Library
from porchlight.live import LiveViews
from porchlight.notifications import Notifications
from porchlight.providers.blink.adapter import BlinkAdapter
from porchlight.providers.blink.local_storage import LocalStorageSource
from porchlight.push import WebPush
from porchlight.retention import Retention, settings_and_usage
from porchlight.review import labels_summary
from porchlight.search import digest as build_digest
from porchlight.search import interpret
from porchlight.security.auth import COOKIE, SESSION_SECONDS, Auth, digest
from porchlight.security.lock import InstanceLock
from porchlight.security.vault import WindowsVault
from porchlight.storage.database import Database
from porchlight.storage.models import (
    Analysis,
    CameraMetadata,
    Capture,
    Event,
    IntegrationState,
    MediaAsset,
    Notification,
    SavedView,
    SettingsRow,
)
from porchlight.storage.work import local_work

logger = logging.getLogger("porchlight")


def error_response(error: ApiError) -> JSONResponse:
    retry_after = int(error.retry_after or 60)
    headers = {"Cache-Control": "no-store"}
    if error.status == 429:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=error.status,
        headers=headers,
        content={
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
            "retry_after_seconds": retry_after if error.status == 429 else None,
            "correlation_id": str(uuid4()),
        },
    )


class BoundaryMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, config: Config):
        super().__init__(app)
        self.config = config

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.headers.get("host", "").lower() not in self.config.allowed_hosts:
            return error_response(
                ApiError(400, "HOST_REJECTED", "Use the local Porchlight address.")
            )
        origin = request.headers.get("origin")
        # The HTML shell contains no account data. Installed launchers and
        # service-worker fetches need not preserve document-navigation metadata.
        # Exempt only GETs to these two public paths, retaining framing denial
        # and every origin/auth/CSRF check for API, media and state changes.
        public_shell = (
            request.method == "GET"
            and request.url.path in {"/", "/index.html"}
            and request.headers.get("sec-fetch-dest")
            not in {"frame", "iframe", "fencedframe", "object", "embed"}
        )
        remote = bool(
            self.config.public_origin
            and request.headers.get("host", "").lower()
            == urlsplit(self.config.public_origin).netloc
        )
        request.state.public_origin = remote
        if remote:
            if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
                return error_response(
                    ApiError(403, "PROXY_REJECTED", "Use the configured local proxy.")
                )
            if (
                request.url.scheme != "https"
                and request.headers.get("x-forwarded-proto") != "https"
            ):
                return error_response(
                    ApiError(403, "HTTPS_REQUIRED", "Use HTTPS for remote access.")
                )
            if origin is not None and origin != self.config.public_origin and not public_shell:
                return error_response(ApiError(403, "ORIGIN_REJECTED", "Open Porchlight directly."))
            if request.url.path in {"/api/v1/setup/bootstrap", "/api/v1/setup/claim"}:
                return error_response(
                    ApiError(403, "LOCAL_SETUP_ONLY", "Complete owner setup locally.")
                )
        if origin is not None and origin not in self.config.allowed_origins and not public_shell:
            return error_response(
                ApiError(403, "ORIGIN_REJECTED", "This origin cannot access Porchlight.")
            )
        if request.headers.get("sec-fetch-site") == "cross-site" and not public_shell:
            return error_response(ApiError(403, "ORIGIN_REJECTED", "Open Porchlight directly."))
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin not in self.config.allowed_origins
        ):
            return error_response(
                ApiError(403, "ORIGIN_REQUIRED", "Open Porchlight directly to make changes.")
            )
        snapshot_route = request.url.path.startswith("/api/v1/live/") and request.url.path.endswith(
            "/snapshot"
        )
        if request.url.path == "/api/v1/imports":
            limit = 256 * 1024 * 1024
        elif request.url.path == "/api/v1/face-detection/suggestions/approve":
            # Reviewed face selections can contain hundreds of box/hash references.
            limit = 1024 * 1024
        elif snapshot_route:
            limit = MAX_SNAPSHOT
        else:
            limit = 16 * 1024
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return error_response(ApiError(400, "INVALID_LENGTH", "Invalid request length."))
        if length < 0 or length > limit:
            return error_response(ApiError(413, "REQUEST_TOO_LARGE", "This request is too large."))
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.url.path != "/api/v1/imports"
        ):
            # Bound chunked JSON too; Content-Length alone cannot bound memory use.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > limit:
                    return error_response(
                        ApiError(413, "REQUEST_TOO_LARGE", "This request is too large.")
                    )
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'; object-src 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if remote:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        lock = InstanceLock(config.data_root)
        lock.acquire()
        db: Database | None = None
        ollama: Ollama | None = None
        heartbeat_task: asyncio.Task[None] | None = None
        blink: BlinkAdapter | None = None
        recording_task: asyncio.Task[None] | None = None
        local_recording_task: asyncio.Task[None] | None = None
        analysis_task: asyncio.Task[None] | None = None
        face_task: asyncio.Task[None] | None = None
        notification_task: asyncio.Task[None] | None = None
        push_task: asyncio.Task[None] | None = None
        controls: CameraControls | None = None
        try:
            db = Database(config.data_root)
            db.migrate()
            with db.session() as session:
                if session.get(SettingsRow, 1) is None:
                    session.add(
                        SettingsRow(
                            id=1,
                            revision=1,
                            values=AppSettings(revision=1, timezone=config.timezone).model_dump(
                                exclude={"revision"}
                            ),
                        )
                    )
                    session.commit()
            app.state.db = db
            app.state.archive = Archive(config, db)
            app.state.retention = Retention(config, db, app.state.archive)
            app.state.archive.recover_deletions()
            app.state.auth = Auth(db)
            app.state.changes = StateChanges(db, app.state.auth.session_valid)
            if config.public_origin and not app.state.auth.owner_exists():
                raise RuntimeError(
                    "Complete loopback owner setup before configuring a public origin."
                )
            ollama = Ollama(config)
            app.state.ollama = ollama
            app.state.analysis = AnalysisPipeline(config, db, ollama)
            app.state.faces = FacePipeline(config, db)
            app.state.evidence = Evidence(config, db)
            app.state.push = WebPush(config, db, WindowsVault(config.data_root, "push"))
            app.state.notifications = Notifications(
                db, app.state.push, app.state.faces.description_contexts
            )
            app.state.analysis.on_completed = app.state.notifications.notify_work
            app.state.faces.on_completed = app.state.notifications.notify_work
            app.state.importer = Importer(config, db)
            app.state.importer.recover()
            app.state.heartbeat = datetime.now(UTC).isoformat()
            app.state.ai_test = None
            blink = BlinkAdapter(db, WindowsVault(config.data_root))
            app.state.blink = blink
            await blink.restore_session()
            controls = CameraControls(db, blink, app.state.auth.session_valid)
            app.state.controls = controls
            app.state.library = Library(config, db)
            await app.state.library.recover()
            app.state.live = LiveViews(config, blink, app.state.library)
            app.state.live.session_valid = app.state.auth.session_valid

            def recording_archived() -> None:
                app.state.analysis.notify_recording()
                app.state.faces.notify_recording()
                app.state.notifications.notify_work()

            recordings = Recordings(
                config,
                db,
                blink,
                app.state.importer,
                on_archived=recording_archived,
            )
            app.state.recordings = recordings
            app.state.local_source = LocalStorageSource(blink)
            app.state.local_recordings = Recordings(
                config,
                db,
                app.state.local_source,
                app.state.importer,
                "blink_local",
                on_archived=recording_archived,
            )
            recording_task = asyncio.create_task(recordings.run())
            local_recording_task = asyncio.create_task(app.state.local_recordings.run())
            analysis_task = asyncio.create_task(app.state.analysis.run())
            face_task = asyncio.create_task(app.state.faces.run())
            notification_task = asyncio.create_task(app.state.notifications.run())
            push_task = asyncio.create_task(app.state.push.run())
            app.state.workers = {
                "recordings": recording_task,
                "local_recordings": local_recording_task,
                "analysis": analysis_task,
                "faces": face_task,
                "notifications": notification_task,
                "push": push_task,
            }

            async def heartbeat() -> None:
                while True:
                    app.state.heartbeat = datetime.now(UTC).isoformat()
                    try:
                        await local_work(app.state.archive.recover_deletions)
                        await local_work(app.state.retention.maintain)
                    except Exception:
                        logger.error('{"event":"local_maintenance_retry"}')
                    await asyncio.sleep(5)

            heartbeat_task = asyncio.create_task(heartbeat())
            logger.info(json.dumps({"event": "application_started", "version": __version__}))
            yield
        finally:
            if hasattr(app.state, "changes"):
                app.state.changes.closing = True
            if controls:
                await controls.close()
            if push_task:
                push_task.cancel()
                with suppress(asyncio.CancelledError):
                    await push_task
            if hasattr(app.state, "live"):
                await app.state.live.stop()
            if analysis_task:
                analysis_task.cancel()
                with suppress(asyncio.CancelledError):
                    await analysis_task
            if face_task:
                face_task.cancel()
                with suppress(asyncio.CancelledError):
                    await face_task
            if recording_task:
                recording_task.cancel()
                with suppress(asyncio.CancelledError):
                    await recording_task
            if local_recording_task:
                local_recording_task.cancel()
                with suppress(asyncio.CancelledError):
                    await local_recording_task
            if heartbeat_task:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task
            if ollama:
                if notification_task:
                    notification_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await notification_task
                await ollama.close()
            if blink:
                await blink.close()
            if db:
                db.close()
            lock.release()
            logger.info(json.dumps({"event": "application_stopped"}))

    app = FastAPI(
        title="Porchlight",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.config = config
    app.add_middleware(BoundaryMiddleware, config=config)

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, __: RequestValidationError) -> JSONResponse:
        # Validation errors include submitted values; never serialize them on secret routes.
        return error_response(
            ApiError(422, "INVALID_INPUT", "Check the supplied fields and try again.")
        )

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, __: Exception) -> JSONResponse:
        logger.error(json.dumps({"event": "request_failed", "code": "INTERNAL_ERROR"}))
        return error_response(
            ApiError(500, "INTERNAL_ERROR", "The request could not be completed.")
        )

    def set_session(response: Response, token: str, request: Request) -> None:
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=bool(request.state.public_origin),
            samesite="strict",
            max_age=SESSION_SECONDS,
            path="/",
        )

    def settings() -> AppSettings:
        with app.state.db.session() as db:
            row = db.get(SettingsRow, 1)
            return AppSettings(revision=row.revision, **row.values)

    def object_categories(ids: list[str]) -> dict[str, list[str]]:
        if not ids:
            return {}
        with app.state.db.session() as db:
            latest = (
                select(Analysis.event_id, func.max(Analysis.revision).label("revision"))
                .where(Analysis.event_id.in_(ids))
                .group_by(Analysis.event_id)
                .subquery()
            )
            rows = db.scalars(
                select(Analysis).join(
                    latest,
                    (Analysis.event_id == latest.c.event_id)
                    & (Analysis.revision == latest.c.revision),
                )
            )
            allowed = {"person", "vehicle", "animal", "package", "other", "unknown"}
            categories = {
                row.event_id: sorted(
                    {
                        entity.get("category")
                        for entity in row.observation.get("entities", [])
                        if entity.get("category") in allowed
                    }
                )
                for row in rows
            }
            for event in db.scalars(select(Event).where(Event.id.in_(ids))):
                if event.corrected_entities is not None:
                    categories[event.id] = sorted(
                        {entity["category"] for entity in event.corrected_entities}
                    )
            return categories

    def event_view(
        event: Event,
        asset: MediaAsset,
        categories: list[str] | None = None,
        face_description: FaceDescription | None = None,
    ) -> EventView:
        if face_description is None:
            face_description = app.state.faces.description_contexts([event.id]).get(
                event.id, FaceDescription()
            )
        summary = event.corrected_summary or event.labels_summary or event.summary
        if (
            not event.corrected_summary
            and not event.labels_summary
            and event.corrected_entities is None
        ):
            summary = personalize_summary(summary, face_description)
        return EventView(
            id=event.id,
            source_type=event.source_type,
            captured_at=event.captured_at,
            discovered_at=event.discovered_at,
            timestamp_quality=event.timestamp_quality,
            media_id=event.media_id,
            analysis_status=event.analysis_status,
            summary=summary,
            corrected_summary=event.corrected_summary,
            ai_summary=event.summary,
            corrected_entities=[
                OwnerEntity.model_validate(entity) for entity in event.corrected_entities
            ]
            if event.corrected_entities is not None
            else None,
            correction_revision=event.correction_revision,
            correction_based_on=event.correction_based_on,
            correction_updated_at=event.correction_updated_at,
            labels_source="owner"
            if event.corrected_entities is not None
            else "ai"
            if event.summary
            else "none",
            favourite=event.favourite,
            note=event.note,
            duration_seconds=asset.duration_seconds,
            camera_id=event.camera_id,
            media_type=asset.media_type,
            historical=event.historical,
            object_categories=categories
            if categories is not None
            else object_categories([event.id]).get(event.id, []),
            recognized_people=list(face_description.names),
        )

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/setup/state", response_model=SetupState)
    def setup_state() -> SetupState:
        return SetupState(owner_created=app.state.auth.owner_exists())

    @app.get("/api/v1/setup/bootstrap", response_model=BootstrapGrant)
    def bootstrap(request: Request) -> BootstrapGrant:
        return BootstrapGrant(
            token=app.state.auth.bootstrap(request),
            expires_in_seconds=max(0, int(app.state.auth.bootstrap_expiry - time.time())),
        )

    @app.post("/api/v1/setup/claim", response_model=SessionView, status_code=201)
    def claim(body: Claim, request: Request, response: Response) -> SessionView:
        credentials = Credentials(login_name=body.login_name, password=body.password)
        token = app.state.auth.create_owner(
            request, credentials, body.bootstrap_token.get_secret_value()
        )
        set_session(response, token, request)
        from porchlight.security.auth import csrf_for

        return SessionView(login_name=body.login_name, csrf_token=csrf_for(token))

    @app.post("/api/v1/auth/login", response_model=SessionView)
    async def login(body: Credentials, request: Request, response: Response) -> SessionView:
        # Revoke the browser's previous session after a successful login.
        token = app.state.auth.login(body)
        if app.state.live.session and app.state.live.session.actor == digest(
            request.cookies.get(COOKIE, "")
        ):
            await app.state.live.stop()
        app.state.auth.logout(request)
        set_session(response, token, request)
        from porchlight.security.auth import csrf_for

        return SessionView(login_name=body.login_name, csrf_token=csrf_for(token))

    @app.get("/api/v1/auth/session", response_model=SessionView)
    def current_session(request: Request) -> SessionView:
        return cast(SessionView, app.state.auth.require(request))

    @app.post("/api/v1/auth/logout", status_code=204)
    async def logout(request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        app.state.auth.logout(request)
        if app.state.live.session and app.state.live.session.actor == digest(
            request.cookies.get(COOKIE, "")
        ):
            await app.state.live.stop()
        response = Response(status_code=204)
        response.delete_cookie(
            COOKIE, path="/", secure=bool(request.state.public_origin), samesite="strict"
        )
        return response

    @app.get("/api/v1/settings", response_model=AppSettings)
    def get_settings(request: Request) -> AppSettings:
        app.state.auth.require(request)
        return settings()

    @app.put("/api/v1/settings", response_model=AppSettings)
    async def update_settings(body: AppSettings, request: Request) -> AppSettings:
        app.state.auth.require(request, csrf=True)
        if body.ai_enabled:
            await app.state.analysis.ready_model(body.ai_model)
        with app.state.db.session() as db:
            # Compare-and-swap prevents concurrent tabs overwriting newer settings.
            from sqlalchemy import update

            previous = db.get(SettingsRow, 1)
            assert previous is not None
            was_enabled = bool(previous.values.get("ai_enabled"))
            if body.retention_enabled and (
                not previous.values.get("retention_enabled")
                or previous.values.get("retention_days", 30) != body.retention_days
            ):
                raise ApiError(
                    409,
                    "RETENTION_PREVIEW_REQUIRED",
                    "Preview local cleanup and confirm its policy before enabling it.",
                )
            result = db.execute(
                update(SettingsRow)
                .where(SettingsRow.id == 1, SettingsRow.revision == body.revision)
                .values(revision=body.revision + 1, values=body.model_dump(exclude={"revision"}))
            )
            if result.rowcount != 1:
                db.rollback()
                raise ApiError(
                    409, "SETTINGS_CHANGED", "Settings changed in another tab. Reload first."
                )
            if body.ai_enabled and not was_enabled:
                control = db.get(IntegrationState, "ai_control")
                if control is None:
                    control = IntegrationState(id="ai_control", values={})
                    db.add(control)
                control.values = {"enabled_at": datetime.now(UTC).isoformat()}
            db.commit()
        app.state.analysis.notify_recording()
        app.state.analysis.wake.set()
        return body.model_copy(update={"revision": body.revision + 1})

    def view_result(row: SavedView) -> SavedViewResult:
        return SavedViewResult(
            id=row.id, name=row.name, filters=EventFilters(**row.filters), created_at=row.created_at
        )

    @app.get("/api/v1/saved-views", response_model=list[SavedViewResult])
    def saved_views(request: Request) -> list[SavedViewResult]:
        app.state.auth.require(request)
        with app.state.db.session() as db:
            return [
                view_result(row)
                for row in db.scalars(
                    select(SavedView).order_by(SavedView.created_at, SavedView.id)
                )
            ]

    @app.get("/api/v1/saved-views/{view_id}", response_model=SavedViewResult)
    def saved_view(view_id: UUID, request: Request) -> SavedViewResult:
        app.state.auth.require(request)
        with app.state.db.session() as db:
            row = db.get(SavedView, str(view_id))
            if not row:
                raise ApiError(404, "VIEW_NOT_FOUND", "This saved view is unavailable.")
            return view_result(row)

    @app.post("/api/v1/saved-views", response_model=SavedViewResult, status_code=201)
    def save_view(body: SavedViewRequest, request: Request) -> SavedViewResult:
        app.state.auth.require(request, csrf=True)
        if body.filters.cursor:
            raise ApiError(422, "VIEW_CURSOR", "Save filters without a page cursor.")
        event_query(body.filters, settings().timezone)
        with app.state.db.session() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            if (db.scalar(select(func.count()).select_from(SavedView)) or 0) >= 20:
                raise ApiError(409, "VIEW_LIMIT", "Remove an unused view before saving another.")
            row = SavedView(
                id=str(uuid4()),
                name=body.name,
                filters=body.filters.model_dump(mode="json", exclude={"cursor"}),
                created_at=datetime.now(UTC).isoformat(),
            )
            db.add(row)
            db.commit()
            return view_result(row)

    @app.delete("/api/v1/saved-views/{view_id}", status_code=204)
    def remove_view(view_id: UUID, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        with app.state.db.session() as db:
            row = db.get(SavedView, str(view_id))
            if not row:
                raise ApiError(404, "VIEW_NOT_FOUND", "This saved view is unavailable.")
            db.delete(row)
            db.commit()
        return Response(status_code=204)

    @app.post("/api/v1/retention/preview", response_model=RetentionPreview)
    def retention_preview(body: RetentionRequest, request: Request) -> RetentionPreview:
        app.state.auth.require(request, csrf=True)
        return cast(RetentionPreview, app.state.retention.preview(body.days))

    @app.post("/api/v1/retention/apply", response_model=RetentionResult)
    def retention_apply(body: RetentionApply, request: Request) -> RetentionResult:
        app.state.auth.require(request, csrf=True)
        return cast(RetentionResult, app.state.retention.apply(body.token, body.enable_automatic))

    @app.get("/api/v1/health", response_model=Health)
    async def health(request: Request) -> Health:
        app.state.auth.require(request)
        with app.state.db.session() as db:
            db.execute(text("SELECT 1"))
            event_count = db.scalar(select(func.count()).select_from(Event)) or 0
            current, used = settings_and_usage(db)
        tools_ready = bool(config.tool_path("ffmpeg") and config.tool_path("ffprobe"))
        try:
            space = shutil.disk_usage(config.data_root).free
        except OSError:
            space = 0
        blink_state: BlinkStatus = app.state.blink.status
        analysis_status: AnalysisStatus = await app.state.analysis.view()
        ai = Component(
            state="ready" if analysis_status.ready else "unverified",
            message=analysis_status.message,
        )
        push_status: PushStatus = await local_work(app.state.push.status)
        reserve = current.reserve_gib * 1024**3
        budget = current.archive_budget_gib * 1024**3
        storage_ready = space >= reserve and used < budget
        archive_status = Component(
            state="ready" if storage_ready else "unavailable",
            message="Local storage available"
            if storage_ready
            else "Saving paused: review the configured space reserve and archive budget.",
        )
        check_rows = await local_work(
            lambda: independent_checks(
                app.state.db,
                blink_state,
                app.state.blink.last_inventory,
                analysis_status,
                push_status,
                archive_status,
                {
                    key: (float(getattr(getattr(app.state, key), "last_tick", 0)), not task.done())
                    for key, task in app.state.workers.items()
                },
            ),
        )
        return Health(
            version=__version__,
            database=Component(state="ready", message="Local database available"),
            archive=archive_status,
            blink=Component(
                state="ready"
                if blink_state.state == "connected"
                else "not_configured"
                if blink_state.state == "not_configured"
                else "unavailable",
                message=blink_state.message,
            ),
            ai=ai,
            media_tools=Component(
                state="ready" if tools_ready else "unavailable",
                message="FFmpeg and ffprobe available"
                if tools_ready
                else "Configure FFmpeg and ffprobe",
            ),
            notifications=Component(
                state="unverified" if push_status.configured else "not_configured",
                message="Local inbox available. " + push_status.message,
            ),
            live_view=Component(
                state="unverified" if config.tool_path("ffmpeg") else "unavailable",
                message="Experimental video-only live view; camera compatibility needs testing.",
            ),
            free_space_bytes=space,
            worker_heartbeat=app.state.heartbeat,
            data_root=str(config.data_root),
            camera_count=len(app.state.blink.cameras),
            event_count=event_count,
            archive_bytes=used,
            reserve_bytes=reserve,
            archive_budget_bytes=budget,
            recording_last_checked_at=app.state.recordings.view().last_checked_at,
            checks=check_rows,
        )

    @app.get("/api/v1/diagnostics/export")
    async def diagnostics(request: Request) -> JSONResponse:
        app.state.auth.require(request)
        report = await local_work(lambda: support_report(config, app.state.db))
        return JSONResponse(
            content=report,
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": 'attachment; filename="porchlight-diagnostics.json"',
            },
        )

    @app.get("/api/v1/ollama/models", response_model=ModelList)
    async def model_list(request: Request) -> ModelList:
        app.state.auth.require(request)
        return await app.state.ollama.models()  # type: ignore[no-any-return]

    @app.get("/api/v1/setup/ai-readiness", response_model=AiReadiness)
    async def ai_readiness(request: Request) -> AiReadiness:
        app.state.auth.require(request)
        return cast(AiReadiness, await local_work(inspect_machine))

    @app.get("/api/v1/setup/guides/{guide}")
    def setup_guide(
        guide: Literal["quick-start", "local-ai", "phone", "direct-https", "cloudflare-backup"],
        request: Request,
    ) -> FileResponse:
        app.state.auth.require(request)
        from porchlight.config import ROOT

        filename = {
            "quick-start": "QUICK_START.md",
            "local-ai": "LOCAL_AI_SETUP.md",
            "phone": "PHONE_SETUP.md",
            "direct-https": "DIRECT_HTTPS.md",
            "cloudflare-backup": "CLOUDFLARE_BACKUP.md",
        }[guide]
        return FileResponse(
            ROOT / "docs" / filename,
            media_type="text/markdown",
            filename=filename,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/ollama/resources", response_model=AiResources)
    async def ai_resources(request: Request) -> AiResources:
        app.state.auth.require(request)
        return cast(AiResources, await app.state.ollama.resources(settings().ai_model))

    @app.post("/api/v1/ollama/test", response_model=ModelTestResult)
    async def test_model(body: ModelTestRequest, request: Request) -> ModelTestResult:
        app.state.auth.require(request, csrf=True)
        result: ModelTestResult = await app.state.ollama.smoke_test(body.model)
        app.state.ai_test = result
        app.state.analysis.record_test(result)
        return result

    @app.get("/api/v1/analysis/status", response_model=AnalysisStatus)
    async def analysis_status(request: Request) -> AnalysisStatus:
        app.state.auth.require(request)
        return cast(AnalysisStatus, await app.state.analysis.view())

    @app.get("/api/v1/face-detection/status", response_model=FaceStatus)
    def face_status(request: Request) -> FaceStatus:
        app.state.auth.require(request)
        return cast(FaceStatus, app.state.faces.view())

    @app.put("/api/v1/face-detection/control", response_model=FaceStatus)
    async def face_control(body: FaceControl, request: Request) -> FaceStatus:
        app.state.auth.require(request, csrf=True)
        return cast(FaceStatus, app.state.faces.set_enabled(body.enabled))

    @app.put("/api/v1/face-detection/auto-enroll", response_model=FaceStatus)
    async def face_auto_enroll(body: FaceControl, request: Request) -> FaceStatus:
        app.state.auth.require(request, csrf=True)
        return cast(FaceStatus, app.state.faces.set_auto_enroll_enabled(body.enabled))

    @app.get("/api/v1/face-detection/people", response_model=PersonProfiles)
    def face_people(request: Request) -> PersonProfiles:
        app.state.auth.require(request)
        return cast(PersonProfiles, app.state.faces.people.list())

    @app.post("/api/v1/face-detection/people", response_model=PersonProfile, status_code=201)
    async def enroll_face(body: FaceEnrollment, request: Request) -> PersonProfile:
        app.state.auth.require(request, csrf=True)
        return cast(
            PersonProfile,
            await app.state.faces.enroll(
                str(body.event_id), body.offset_ms, body.face_index, body.name, body.person_id
            ),
        )

    @app.patch("/api/v1/face-detection/people/{person_id}", response_model=PersonProfile)
    def rename_face_person(person_id: UUID, body: PersonRename, request: Request) -> PersonProfile:
        app.state.auth.require(request, csrf=True)
        return cast(PersonProfile, app.state.faces.people.rename(person_id, body.name))

    @app.delete("/api/v1/face-detection/people/{person_id}", status_code=204)
    def delete_face_person(person_id: UUID, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        app.state.faces.people.delete(person_id)
        return Response(status_code=204)

    @app.get("/api/v1/face-detection/candidates", response_model=FaceCandidates)
    def face_candidates(request: Request) -> FaceCandidates:
        app.state.auth.require(request)
        return cast(FaceCandidates, app.state.faces.candidates())

    @app.get("/api/v1/face-detection/gallery", response_model=FaceGallery)
    async def face_gallery(request: Request, offset: int = Query(default=0, ge=0)) -> FaceGallery:
        app.state.auth.require(request)
        return cast(FaceGallery, await app.state.faces.gallery(offset))

    @app.post("/api/v1/face-detection/rescan-recent", response_model=FaceRescan)
    def rescan_recent_faces(request: Request) -> FaceRescan:
        app.state.auth.require(request, csrf=True)
        return cast(FaceRescan, app.state.faces.rescan_recent())

    @app.get("/api/v1/events/{event_id}/faces", response_model=FaceResult)
    def event_faces(event_id: UUID, request: Request) -> FaceResult:
        app.state.auth.require(request)
        return cast(FaceResult, app.state.faces.result(str(event_id)))

    @app.get("/api/v1/events/{event_id}/faces/frames/{offset_ms}")
    async def face_sample_frame(
        event_id: UUID, offset_ms: Annotated[int, Path(ge=0, le=300000)], request: Request
    ) -> Response:
        app.state.auth.require(request)
        jpeg = await app.state.faces.sample_frame(str(event_id), offset_ms)
        return Response(
            jpeg, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"}
        )

    @app.post("/api/v1/face-detection/people/batch", response_model=PersonProfile, status_code=201)
    async def enroll_face_batch(body: FaceEnrollmentBatch, request: Request) -> PersonProfile:
        app.state.auth.require(request, csrf=True)
        return cast(
            PersonProfile,
            await app.state.faces.enroll_many(body.samples, body.name, body.person_id),
        )

    @app.post("/api/v1/face-detection/suggestions/approve", response_model=FaceApprovalResult)
    def approve_face_suggestions(body: FaceApproval, request: Request) -> FaceApprovalResult:
        app.state.auth.require(request, csrf=True)
        return cast(
            FaceApprovalResult, app.state.faces.approve_suggestions(body.person_id, body.faces)
        )

    @app.get("/api/v1/events/{event_id}/faces/thumbnails/{offset_ms}/{face_index}")
    async def face_thumbnail(
        event_id: UUID,
        offset_ms: Annotated[int, Path(ge=0, le=300000)],
        face_index: Annotated[int, Path(ge=0, le=24)],
        request: Request,
    ) -> Response:
        app.state.auth.require(request)
        jpeg = await app.state.faces.thumbnail(str(event_id), offset_ms, face_index)
        return Response(
            jpeg, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"}
        )

    @app.post("/api/v1/events/{event_id}/faces", response_model=FaceResult, status_code=202)
    async def detect_event_faces(
        event_id: UUID, body: AnalysisRequest, request: Request
    ) -> FaceResult:
        app.state.auth.require(request, csrf=True)
        return cast(FaceResult, app.state.faces.enqueue(str(event_id), reanalyze=body.reanalyze))

    @app.get("/api/v1/events/{event_id}/analysis", response_model=AnalysisView | None)
    def event_analysis(event_id: UUID, request: Request) -> AnalysisView | None:
        app.state.auth.require(request)
        get_event(event_id, request)
        return cast(AnalysisView | None, app.state.analysis.latest(str(event_id)))

    @app.post("/api/v1/events/{event_id}/analyze", response_model=AnalysisJobView, status_code=202)
    async def analyze_event(
        event_id: UUID, body: AnalysisRequest, request: Request
    ) -> AnalysisJobView:
        app.state.auth.require(request, csrf=True)
        return cast(
            AnalysisJobView, await app.state.analysis.request(str(event_id), body.reanalyze)
        )

    @app.get("/api/v1/events/{event_id}/analysis/{revision}/frames/{frame_id}")
    async def analysis_frame(
        event_id: UUID,
        revision: Annotated[int, Path(ge=1)],
        frame_id: Annotated[str, Path(pattern=r"^f[0-9]{3}$")],
        request: Request,
    ) -> Response:
        app.state.auth.require(request)
        image = await app.state.evidence.get(str(event_id), revision, frame_id)
        return Response(image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/events", response_model=EventList)
    def list_events(request: Request, filters: Annotated[EventFilters, Query()]) -> EventList:
        app.state.auth.require(request)
        with app.state.db.session() as db:
            rows = timeline_rows(db, filters, settings().timezone)
            ids = [row[0].id for row in rows[:30] if not isinstance(row, Capture)]
            categories = object_categories(ids)
            recognized = app.state.faces.description_contexts(ids)
            items = [
                capture_event(row)
                if isinstance(row, Capture)
                else event_view(
                    row[0],
                    row[1],
                    categories.get(row[0].id, []),
                    recognized.get(row[0].id, FaceDescription()),
                )
                for row in rows[:30]
            ]
            cursor = None
            if len(rows) > 30:
                last = items[-1]
                cursor = (
                    f"{'c' if last.capture else 'e'}:{last.id}"
                    if filters.include_captures
                    else last.id
                )
            return EventList(items=items, next_cursor=cursor)

    @app.post("/api/v1/search/interpret", response_model=SearchPreview)
    async def search_interpret(body: SearchRequest, request: Request) -> SearchPreview:
        app.state.auth.require(request, csrf=True)
        values = settings()
        await app.state.analysis.ready_model(values.ai_model)
        return await interpret(
            app.state.ollama, values.ai_model, body.query, camera_list().items, values.timezone
        )

    @app.get("/api/v1/digests/daily", response_model=DailyDigest)
    def daily_digest(day: date, request: Request) -> DailyDigest:
        app.state.auth.require(request)
        return build_digest(app.state.db, day, settings().timezone)

    @app.get("/api/v1/notifications", response_model=InboxView)
    def inbox(request: Request, cursor: UUID | None = None) -> InboxView:
        app.state.auth.require(request)
        return cast(InboxView, app.state.notifications.inbox(str(cursor) if cursor else None))

    @app.get("/api/v1/push", response_model=PushStatus)
    async def push_status(request: Request) -> PushStatus:
        app.state.auth.require(request)
        return cast(PushStatus, await local_work(app.state.push.status))

    @app.post("/api/v1/push/configure", response_model=PushStatus)
    async def configure_push(request: Request) -> PushStatus:
        app.state.auth.require(request, csrf=True)
        if request.state.public_origin:
            raise ApiError(403, "LOCAL_SETUP_REQUIRED", "Create push keys from the PC's local app.")
        return cast(PushStatus, await local_work(app.state.push.configure))

    @app.post("/api/v1/push/deliveries/{delivery_id}/receipt", status_code=204)
    async def push_receipt(delivery_id: UUID, body: PushReceipt, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        await local_work(lambda: app.state.push.receipt(str(delivery_id), body))
        return Response(status_code=204)

    @app.post("/api/v1/push/devices", response_model=PushStatus, status_code=201)
    async def pair_push(body: PushPairRequest, request: Request) -> PushStatus:
        app.state.auth.require(request, csrf=True)
        if not request.state.public_origin:
            raise ApiError(
                409, "HTTPS_ORIGIN_REQUIRED", "Pair the browser at the configured HTTPS address."
            )
        return cast(PushStatus, await local_work(lambda: app.state.push.pair(body)))

    @app.delete("/api/v1/push/devices/{device_id}", status_code=204)
    async def revoke_push(device_id: UUID, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        await local_work(lambda: app.state.push.revoke(str(device_id)))
        return Response(status_code=204)

    @app.post("/api/v1/push/devices/{device_id}/test", response_model=PushStatus, status_code=202)
    async def test_push(device_id: UUID, request: Request) -> PushStatus:
        app.state.auth.require(request, csrf=True)
        return cast(PushStatus, await local_work(lambda: app.state.push.test(str(device_id))))

    @app.post("/api/v1/notifications/{notification_id}/read", status_code=204)
    def mark_read(notification_id: UUID, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        with app.state.db.session() as db:
            row = db.get(Notification, str(notification_id))
            if not row:
                raise ApiError(404, "NOTIFICATION_NOT_FOUND", "This notification is unavailable.")
            row.read = True
            db.commit()
        return Response(status_code=204)

    @app.post("/api/v1/notifications/test", response_model=InboxView, status_code=201)
    def test_inbox(request: Request) -> InboxView:
        app.state.auth.require(request, csrf=True)
        with app.state.db.session() as db:
            db.add(
                Notification(
                    id=str(uuid4()),
                    event_id=None,
                    rule_id=None,
                    tag=f"test:{uuid4()}",
                    title="Porchlight test",
                    body="This is a local inbox test. "
                    "It does not verify background phone delivery.",
                    created_at=datetime.now(UTC).isoformat(),
                    read=False,
                )
            )
            db.commit()
        return cast(InboxView, app.state.notifications.inbox())

    @app.post("/api/v1/notifications/snooze", status_code=204)
    def snooze_notifications(body: SnoozeRequest, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        app.state.notifications.snooze(body.minutes)
        return Response(status_code=204)

    @app.get("/api/v1/notification-rules", response_model=list[RuleView])
    def notification_rules(request: Request) -> list[RuleView]:
        app.state.auth.require(request)
        return cast(list[RuleView], app.state.notifications.rules())

    @app.post("/api/v1/notification-rules", response_model=RuleView, status_code=201)
    def create_rule(body: RuleBody, request: Request) -> RuleView:
        app.state.auth.require(request, csrf=True)
        return cast(RuleView, app.state.notifications.save_rule(body.definition))

    @app.put("/api/v1/notification-rules/{rule_id}", response_model=RuleView)
    def update_rule(rule_id: UUID, body: RuleUpdate, request: Request) -> RuleView:
        app.state.auth.require(request, csrf=True)
        return cast(
            RuleView,
            app.state.notifications.save_rule(
                body.definition, str(rule_id), body.expected_revision
            ),
        )

    @app.delete("/api/v1/notification-rules/{rule_id}", status_code=204)
    def delete_rule(
        rule_id: UUID, request: Request, expected_revision: int = Query(ge=1)
    ) -> Response:
        app.state.auth.require(request, csrf=True)
        app.state.notifications.delete_rule(str(rule_id), expected_revision)
        return Response(status_code=204)

    @app.get("/api/v1/events/{event_id}", response_model=EventView)
    def get_event(event_id: UUID, request: Request) -> EventView:
        app.state.auth.require(request)
        with app.state.db.session() as db:
            event = db.get(Event, str(event_id))
            asset = db.get(MediaAsset, event.media_id) if event else None
            if event is None or asset is None:
                raise ApiError(404, "EVENT_NOT_FOUND", "This recording is unavailable.")
            return event_view(event, asset)

    @app.get("/api/v1/events/{event_id}/match", response_model=EventView | None)
    def matching_event(
        event_id: UUID, request: Request, filters: Annotated[EventFilters, Query()]
    ) -> EventView | None:
        """Refresh one loaded archive row using exactly the current filter semantics."""
        app.state.auth.require(request)
        with app.state.db.session() as db:
            row = db.execute(
                event_query(filters, settings().timezone).where(Event.id == str(event_id))
            ).first()
            return event_view(*row) if row else None

    @app.put("/api/v1/events/{event_id}/labels", response_model=EventView)
    def correct_labels(event_id: UUID, body: LabelCorrection, request: Request) -> EventView:
        app.state.auth.require(request, csrf=True)
        with app.state.db.session() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            event = db.get(Event, str(event_id))
            if event is None:
                raise ApiError(404, "EVENT_NOT_FOUND", "This recording is unavailable.")
            if event.correction_revision != body.revision:
                raise ApiError(
                    409,
                    "LABELS_CHANGED",
                    "These labels changed in another view. Reload labels before saving.",
                )
            event.corrected_entities = (
                [entity.model_dump() for entity in body.entities]
                if body.entities is not None
                else None
            )
            event.labels_summary = (
                labels_summary(body.entities) if body.entities is not None else None
            )
            event.correction_revision += 1
            if body.entities is not None and body.based_on is not None:
                if not db.scalar(
                    select(Analysis.id).where(
                        Analysis.event_id == event.id, Analysis.revision == body.based_on
                    )
                ):
                    raise ApiError(
                        422, "LABEL_BASIS_UNAVAILABLE", "The referenced AI revision is unavailable."
                    )
            event.correction_based_on = body.based_on if body.entities is not None else None
            event.correction_updated_at = datetime.now(UTC).isoformat()
            db.commit()
        # Updating a review never queues inference, changes the AI revision or emits an alert.
        return get_event(event_id, request)

    @app.patch("/api/v1/events/{event_id}/annotation", response_model=EventView)
    def annotate(event_id: UUID, body: Annotation, request: Request) -> EventView:
        app.state.auth.require(request, csrf=True)
        with app.state.db.session() as db:
            event = db.get(Event, str(event_id))
            if event is None:
                raise ApiError(404, "EVENT_NOT_FOUND", "This recording is unavailable.")
            event.favourite, event.note = body.favourite, body.note
            if "corrected_summary" in body.model_fields_set:
                event.corrected_summary = (
                    body.corrected_summary.strip() or None if body.corrected_summary else None
                )
            db.commit()
        return get_event(event_id, request)

    @app.delete("/api/v1/events/{event_id}", status_code=204)
    def delete_event(event_id: UUID, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        app.state.archive.delete_event(str(event_id))
        return Response(status_code=204)

    @app.post("/api/v1/imports", response_model=EventView, status_code=201)
    async def import_clip(request: Request) -> EventView:
        app.state.auth.require(request, csrf=True)
        try:
            event_id = await asyncio.wait_for(
                app.state.importer.import_request(request), timeout=90
            )
        except TimeoutError as exc:
            raise ApiError(
                408, "IMPORT_TIMEOUT", "The import timed out. Try a shorter recording."
            ) from exc
        return get_event(UUID(event_id), request)

    @app.head("/api/v1/media/{asset_id}", include_in_schema=False)
    @app.get("/api/v1/media/{asset_id}")
    def media(asset_id: UUID, request: Request) -> FileResponse:
        app.state.auth.require(request)
        with app.state.db.session() as db:
            asset = db.get(MediaAsset, str(asset_id))
            if asset is None:
                raise ApiError(404, "MEDIA_NOT_FOUND", "This recording is unavailable.")
            path = (config.data_root / asset.relative_path).resolve()
            if (
                not path.is_relative_to((config.data_root / "media").resolve())
                or not path.is_file()
            ):
                raise ApiError(404, "MEDIA_NOT_FOUND", "The local recording file is unavailable.")
            return FileResponse(
                path, media_type=asset.media_type, headers={"Cache-Control": "no-store"}
            )

    thumbnails = Thumbnails(config)

    @app.get("/api/v1/events/{event_id}/notification-thumbnail")
    async def notification_thumbnail(event_id: UUID, request: Request) -> Response:
        app.state.auth.require(request)
        with app.state.db.session() as db:
            event = db.get(Event, str(event_id))
            asset = db.get(MediaAsset, event.media_id) if event and event.media_id else None
            if asset is None:
                raise ApiError(404, "MEDIA_NOT_FOUND", "This recording is unavailable.")
            path = (config.data_root / asset.relative_path).resolve()
            asset_id, media_type = asset.id, asset.media_type
        image = await thumbnails.get(path, asset_id, media_type)
        return Response(image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/media/{asset_id}/thumbnail")
    async def thumbnail(asset_id: UUID, request: Request) -> Response:
        app.state.auth.require(request)
        with app.state.db.session() as db:
            asset = db.get(MediaAsset, str(asset_id))
            if asset is None:
                raise ApiError(404, "MEDIA_NOT_FOUND", "This recording is unavailable.")
            path = (config.data_root / asset.relative_path).resolve()
            media_type = asset.media_type
        image = await thumbnails.get(path, str(asset_id), media_type)
        return Response(image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    def camera_list() -> CameraList:
        with app.state.db.session() as db:
            ranked = (
                select(
                    Event.camera_id,
                    Event.id.label("event_id"),
                    Event.media_id,
                    Event.captured_at,
                    Event.discovered_at,
                    Event.source_type,
                    Event.summary,
                    Event.corrected_summary,
                    Event.labels_summary,
                    Event.analysis_status,
                    func.row_number()
                    .over(
                        partition_by=Event.camera_id,
                        order_by=(
                            func.coalesce(Event.captured_at, Event.discovered_at).desc(),
                            Event.id.desc(),
                        ),
                    )
                    .label("rank"),
                )
                .join(MediaAsset, Event.media_id == MediaAsset.id)
                .where(
                    Event.source_type.in_(["blink_cloud", "blink_local"]),
                    Event.camera_id.is_not(None),
                )
                .subquery()
            )
            latest = {
                row.camera_id: CameraRecording(
                    summary=row.corrected_summary or row.labels_summary or row.summary,
                    summary_source="owner"
                    if row.corrected_summary or row.labels_summary
                    else "ai"
                    if row.summary
                    else "none",
                    analysis_status=row.analysis_status,
                    source_type=row.source_type,
                    event_id=row.event_id,
                    media_id=row.media_id,
                    captured_at=row.captured_at,
                    discovered_at=row.discovered_at,
                )
                for row in db.execute(select(ranked).where(ranked.c.rank == 1))
            }
            metadata = {row.camera_id: row for row in db.scalars(select(CameraMetadata))}
        return CameraList(
            items=[
                camera.model_copy(
                    update={
                        "recording_access": (
                            "local_archived"
                            if latest[camera.id].source_type == "blink_local"
                            else "cloud_archived"
                        )
                        if camera.id in latest
                        else "unverified",
                        "latest_recording": latest.get(camera.id),
                        "name": metadata[camera.id].name or camera.name
                        if camera.id in metadata
                        else camera.name,
                        "group": metadata[camera.id].group if camera.id in metadata else "",
                    }
                )
                for camera in app.state.blink.cameras
            ]
        )

    @app.get("/api/v1/cameras", response_model=CameraList)
    def cameras(request: Request) -> CameraList:
        app.state.auth.require(request)
        return camera_list()

    @app.patch("/api/v1/cameras/{camera_id}/metadata", response_model=CameraList)
    def camera_metadata(camera_id: UUID, body: LocalCameraMetadata, request: Request) -> CameraList:
        app.state.auth.require(request, csrf=True)
        if not any(camera.id == str(camera_id) for camera in app.state.blink.cameras):
            raise ApiError(404, "CAMERA_NOT_FOUND", "This camera is unavailable.")
        with app.state.db.session() as db:
            row = db.get(CameraMetadata, str(camera_id))
            if not row:
                row = CameraMetadata(camera_id=str(camera_id), name="", group="")
                db.add(row)
            row.name, row.group = body.name.strip(), body.group.strip()
            db.commit()
        return camera_list()

    @app.get("/api/v1/integrations/blink/status", response_model=BlinkStatus)
    def blink_status(request: Request) -> BlinkStatus:
        app.state.auth.require(request)
        return cast(BlinkStatus, app.state.blink.status)

    @app.post("/api/v1/integrations/blink/auth/start", response_model=BlinkStatus)
    async def blink_start(body: BlinkCredentials, request: Request) -> BlinkStatus:
        app.state.auth.require(request, csrf=True)
        await app.state.live.stop()
        return cast(
            BlinkStatus,
            await app.state.blink.begin_auth(body, digest(request.cookies.get(COOKIE, ""))),
        )

    @app.post("/api/v1/integrations/blink/auth/verify", response_model=BlinkStatus)
    async def blink_verify(body: BlinkVerification, request: Request) -> BlinkStatus:
        app.state.auth.require(request, csrf=True)
        return cast(
            BlinkStatus,
            await app.state.blink.complete_auth(body, digest(request.cookies.get(COOKIE, ""))),
        )

    @app.post("/api/v1/integrations/blink/inventory/refresh", response_model=CameraList)
    async def refresh_inventory(request: Request) -> CameraList:
        app.state.auth.require(request, csrf=True)
        await app.state.blink.discover_inventory()
        return camera_list()

    @app.post(
        "/api/v1/cameras/{camera_id}/commands", response_model=CameraCommandView, status_code=202
    )
    async def camera_command(
        camera_id: UUID, body: CameraCommandRequest, request: Request
    ) -> CameraCommandView:
        app.state.auth.require(request, csrf=True)
        return cast(
            CameraCommandView,
            app.state.controls.submit(
                str(camera_id), body, digest(request.cookies.get(COOKIE, ""))
            ),
        )

    @app.get("/api/v1/cameras/{camera_id}/commands/latest", response_model=CameraCommandView | None)
    def latest_command(
        camera_id: UUID,
        request: Request,
        operation: Literal["network_armed", "motion_enabled"] | None = None,
    ) -> CameraCommandView | None:
        app.state.auth.require(request)
        return cast(CameraCommandView | None, app.state.controls.latest(str(camera_id), operation))

    @app.get("/api/v1/camera-commands/{command_id}", response_model=CameraCommandView)
    def command_status(command_id: UUID, request: Request) -> CameraCommandView:
        app.state.auth.require(request)
        return cast(CameraCommandView, app.state.controls.get(str(command_id)))

    @app.post("/api/v1/camera-commands/{command_id}/verify", response_model=CameraCommandView)
    async def verify_command(command_id: UUID, request: Request) -> CameraCommandView:
        app.state.auth.require(request, csrf=True)
        return cast(CameraCommandView, await app.state.controls.verify(str(command_id)))

    def local_recording_status() -> LocalRecordingStatus:
        return LocalRecordingStatus(
            modules=app.state.blink.local_modules,
            sync=app.state.local_recordings.view(),
            eligible=bool(app.state.blink.local_targets),
        )

    @app.get("/api/v1/integrations/blink/local-recordings", response_model=LocalRecordingStatus)
    def local_recordings(request: Request) -> LocalRecordingStatus:
        app.state.auth.require(request)
        return local_recording_status()

    @app.post(
        "/api/v1/integrations/blink/local-sync",
        response_model=LocalRecordingStatus,
        status_code=202,
    )
    def local_sync(body: RecordingControl, request: Request) -> LocalRecordingStatus:
        app.state.auth.require(request, csrf=True)
        if body.enabled and not app.state.blink.local_targets:
            raise ApiError(
                409,
                "LOCAL_STORAGE_NOT_READY",
                "Blink must report enabled, active local storage before a local sync test.",
            )
        app.state.local_recordings.control(body.enabled)
        return local_recording_status()

    @app.get("/api/v1/integrations/blink/recordings", response_model=RecordingSync)
    def recording_status(request: Request) -> RecordingSync:
        app.state.auth.require(request)
        return cast(RecordingSync, app.state.recordings.view())

    @app.post("/api/v1/cameras/{camera_id}/live", response_model=LiveSession, status_code=202)
    async def start_live(camera_id: UUID, request: Request) -> LiveSession:
        app.state.auth.require(request, csrf=True)
        if str(camera_id) not in app.state.blink.live_cameras:
            raise ApiError(409, "LIVE_UNSUPPORTED", "Live view is unavailable for this camera.")
        return cast(
            LiveSession,
            await app.state.live.start(
                str(camera_id),
                digest(request.cookies.get(COOKIE, "")),
                next(
                    (
                        camera.name
                        for camera in app.state.blink.cameras
                        if camera.id == str(camera_id)
                    ),
                    "Camera",
                ),
            ),
        )

    @app.post("/api/v1/live/{session_id}/record", response_model=CaptureView, status_code=201)
    async def start_live_recording(session_id: UUID, request: Request) -> CaptureView:
        app.state.auth.require(request, csrf=True)
        return cast(
            CaptureView,
            await app.state.live.start_recording(
                str(session_id), digest(request.cookies.get(COOKIE, ""))
            ),
        )

    @app.post("/api/v1/live/{session_id}/record/stop", response_model=CaptureView)
    async def stop_live_recording(session_id: UUID, request: Request) -> CaptureView:
        app.state.auth.require(request, csrf=True)
        return cast(
            CaptureView,
            await app.state.live.stop_recording(
                str(session_id), digest(request.cookies.get(COOKIE, ""))
            ),
        )

    @app.post("/api/v1/live/{session_id}/snapshot", response_model=CaptureView, status_code=201)
    async def live_snapshot(session_id: UUID, request: Request) -> CaptureView:
        app.state.auth.require(request, csrf=True)
        if request.headers.get("content-type", "").split(";")[0] != "image/jpeg":
            raise ApiError(415, "JPEG_REQUIRED", "Use a JPEG snapshot.")
        return cast(
            CaptureView,
            await app.state.live.snapshot(
                str(session_id), digest(request.cookies.get(COOKIE, "")), await request.body()
            ),
        )

    @app.get("/api/v1/library", response_model=CaptureList)
    def library_list(request: Request, cursor: UUID | None = None) -> CaptureList:
        app.state.auth.require(request)
        return cast(CaptureList, app.state.library.listing(str(cursor) if cursor else None))

    @app.get("/api/v1/library/{capture_id}", response_model=CaptureView)
    def library_capture(capture_id: UUID, request: Request) -> CaptureView:
        app.state.auth.require(request)
        return cast(CaptureView, app.state.library.get(str(capture_id)))

    @app.patch("/api/v1/library/{capture_id}/favourite", response_model=CaptureView)
    def favourite_capture(
        capture_id: UUID, body: FavouriteRequest, request: Request
    ) -> CaptureView:
        app.state.auth.require(request, csrf=True)
        with app.state.db.session() as db:
            capture = db.get(Capture, str(capture_id))
            if not capture:
                raise ApiError(404, "CAPTURE_NOT_FOUND", "This capture is unavailable.")
            capture.favourite = body.favourite
            db.commit()
        return cast(CaptureView, app.state.library.get(str(capture_id)))

    @app.delete("/api/v1/library/{capture_id}", status_code=204)
    def delete_capture(capture_id: UUID, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        app.state.archive.delete_capture(str(capture_id))
        return Response(status_code=204)

    @app.head("/api/v1/library/{capture_id}/media", include_in_schema=False)
    @app.get("/api/v1/library/{capture_id}/media")
    def library_media(capture_id: UUID, request: Request) -> FileResponse:
        app.state.auth.require(request)
        path, media_type = app.state.library.media(str(capture_id))
        return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/library/{capture_id}/thumbnail")
    async def library_thumbnail(capture_id: UUID, request: Request) -> Response:
        app.state.auth.require(request)
        path, media_type = app.state.library.media(str(capture_id))
        image = (
            path.read_bytes()
            if media_type == "image/jpeg"
            else await thumbnails.get(path, str(capture_id))
        )
        return Response(image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/live/{session_id}", response_model=LiveSession)
    def live_status(session_id: UUID, request: Request) -> LiveSession:
        app.state.auth.require(request)
        return cast(
            LiveSession,
            app.state.live.status(str(session_id), digest(request.cookies.get(COOKIE, ""))),
        )

    @app.post("/api/v1/live/{session_id}/heartbeat", response_model=LiveSession)
    def live_heartbeat(session_id: UUID, request: Request) -> LiveSession:
        app.state.auth.require(request, csrf=True)
        return cast(
            LiveSession,
            app.state.live.touch(str(session_id), digest(request.cookies.get(COOKIE, ""))),
        )

    @app.post("/api/v1/live/{session_id}/stop", status_code=204)
    async def stop_live(session_id: UUID, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        await app.state.live.stop(str(session_id), digest(request.cookies.get(COOKIE, "")))
        return Response(status_code=204)

    @app.post("/api/v1/live/{session_id}/trust-certificate", status_code=204)
    def trust_live_certificate(session_id: UUID, request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        current = app.state.live.require(str(session_id), digest(request.cookies.get(COOKIE, "")))
        if not current.certificate_sha256 or current.state != "failed":
            raise ApiError(
                409, "LIVE_CERT_REVIEW_REQUIRED", "There is no certificate awaiting review."
            )
        app.state.blink.trust_live_certificate(current.certificate_sha256)
        return Response(status_code=204)

    @app.post("/api/v1/live/certificates/revoke", status_code=204)
    async def revoke_live_certificates(request: Request) -> Response:
        app.state.auth.require(request, csrf=True)
        await app.state.live.stop()
        app.state.blink.revoke_live_certificates()
        return Response(status_code=204)

    @app.get("/api/v1/live/{session_id}/media")
    async def live_media(session_id: UUID, request: Request) -> StreamingResponse:
        app.state.auth.require(request)
        current = app.state.live.require(str(session_id), digest(request.cookies.get(COOKIE, "")))
        if current.state in {"ended", "failed"}:
            raise ApiError(410, "LIVE_ENDED", "This live session has ended.")
        if current.attached:
            raise ApiError(409, "LIVE_ATTACHED", "This live session already has a player.")
        if request.headers.get("range"):
            raise ApiError(400, "LIVE_RANGE_REJECTED", "Live video does not support seeking.")
        current.attached = True
        try:
            await asyncio.wait_for(current.initialized.wait(), 25)
        except TimeoutError:
            await app.state.live.stop(current.id, current.actor)
            raise ApiError(503, "LIVE_NO_VIDEO", "No video arrived from the camera.") from None
        if not current.fragments.initialized:
            raise ApiError(410, "LIVE_ENDED", "This live session has ended.")
        return StreamingResponse(
            app.state.live.media(current), media_type=app.state.live.view(current).mime_type
        )

    @app.post("/api/v1/integrations/blink/sync", response_model=RecordingSync, status_code=202)
    def recording_control(body: RecordingControl, request: Request) -> RecordingSync:
        app.state.auth.require(request, csrf=True)
        return cast(RecordingSync, app.state.recordings.control(body.enabled))

    @app.post("/api/v1/integrations/blink/history", response_model=RecordingSync, status_code=202)
    def recording_history(body: HistoryControl, request: Request) -> RecordingSync:
        app.state.auth.require(request, csrf=True)
        return cast(RecordingSync, app.state.recordings.history(body))

    @app.get("/api/v1/openapi.json", include_in_schema=False)
    def openapi(request: Request) -> dict[str, Any]:
        app.state.auth.require(request)
        return app.openapi()

    @app.get("/api/v1/stream", responses={200: {"content": {"text/event-stream": {}}}})
    async def state_stream(request: Request) -> StreamingResponse:
        app.state.auth.require(request)
        changes: StateChanges = app.state.changes
        actor = digest(request.cookies.get(COOKIE, ""))
        token = changes.reserve(actor)
        return StreamingResponse(
            changes.stream(request, actor, token, request.headers.get("last-event-id")),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            background=BackgroundTask(changes.release, token),
        )

    if (config.web_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=config.web_dist / "assets"), name="assets")

    @app.head("/{path:path}", include_in_schema=False)
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith(("api/", "health/")):
            raise ApiError(404, "NOT_FOUND", "This endpoint is unavailable.")
        public_files = {
            "manifest.webmanifest": "application/manifest+json",
            "sw.js": "text/javascript",
            "favicon-v4.ico": "image/x-icon",
            "icons/porchlight-mark-v4.png": "image/png",
            "icons/porchlight-badge-v4-96.png": "image/png",
            "icons/porchlight-v4-16.png": "image/png",
            "icons/porchlight-v4-32.png": "image/png",
            "icons/porchlight-v4-48.png": "image/png",
            "icons/porchlight-v4-180.png": "image/png",
            "icons/porchlight-v4-192.png": "image/png",
            "icons/porchlight-v4-512.png": "image/png",
            "icons/porchlight-v4-maskable-512.png": "image/png",
            "icons/porchlight-192.png": "image/png",
            "icons/porchlight-512.png": "image/png",
            "icons/porchlight-mark-v3.png": "image/png",
            "icons/porchlight-v3-192.png": "image/png",
            "icons/porchlight-v3-512.png": "image/png",
            "icons/porchlight-v3-maskable-512.png": "image/png",
        }
        if path in public_files:
            asset = config.web_dist / path
            if not asset.is_file():
                raise ApiError(404, "NOT_FOUND", "This asset is unavailable.")
            return FileResponse(
                asset, media_type=public_files[path], headers={"Cache-Control": "no-store"}
            )
        if path.startswith("icons/"):
            raise ApiError(404, "NOT_FOUND", "This asset is unavailable.")
        index = config.web_dist / "index.html"
        if not index.is_file():
            raise ApiError(503, "FRONTEND_NOT_BUILT", "Run bootstrap.ps1 to build the interface.")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app
