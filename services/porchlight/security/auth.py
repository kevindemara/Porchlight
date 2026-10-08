from __future__ import annotations

import hashlib
import secrets
import threading
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from porchlight.api.contracts import ApiError, Credentials, SessionView
from porchlight.storage.database import Database
from porchlight.storage.models import LoginAttempt, Owner, Session

COOKIE = "porchlight_session"
SESSION_SECONDS = 12 * 60 * 60
hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for(token: str) -> str:
    return digest("porchlight-csrf-v1:" + token)


class Auth:
    def __init__(self, db: Database):
        self.db = db
        self.bootstrap_token = secrets.token_urlsafe(32)
        self.bootstrap_expiry = time.time() + 15 * 60
        self.lock = threading.Lock()

    def owner_exists(self) -> bool:
        with self.db.session() as db:
            return db.get(Owner, "owner") is not None

    def bootstrap(self, request: Request) -> str:
        self.require_loopback(request)
        if request.headers.get("x-porchlight-bootstrap") != "local-setup":
            raise ApiError(403, "BOOTSTRAP_FORBIDDEN", "Open setup in the local Porchlight app.")
        if self.owner_exists():
            raise ApiError(409, "ALREADY_CLAIMED", "A local owner already exists. Sign in instead.")
        if time.time() >= self.bootstrap_expiry:
            raise ApiError(409, "BOOTSTRAP_EXPIRED", "Restart Porchlight to renew local setup.")
        return self.bootstrap_token

    @staticmethod
    def require_loopback(request: Request) -> None:
        if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
            raise ApiError(403, "LOCAL_SETUP_ONLY", "Owner setup requires local access.")

    def create_owner(self, request: Request, credentials: Credentials, token: str) -> str:
        self.require_loopback(request)
        with self.lock:
            if self.owner_exists():
                raise ApiError(409, "ALREADY_CLAIMED", "A local owner already exists.")
            if time.time() >= self.bootstrap_expiry or not secrets.compare_digest(
                token, self.bootstrap_token
            ):
                raise ApiError(403, "INVALID_BOOTSTRAP", "Local setup expired. Restart Porchlight.")
            if len(credentials.password.get_secret_value()) < 12:
                raise ApiError(
                    422, "WEAK_PASSWORD", "Use at least 12 characters for your password."
                )
            with self.db.session() as db:
                db.add(
                    Owner(
                        id="owner",
                        login_name=credentials.login_name,
                        password_hash=hasher.hash(credentials.password.get_secret_value()),
                        created_at=time.time(),
                    )
                )
                try:
                    db.commit()
                except IntegrityError as exc:
                    raise ApiError(409, "ALREADY_CLAIMED", "A local owner already exists.") from exc
            self.bootstrap_token = ""
        return self.issue_session()

    def login(self, credentials: Credentials) -> str:
        # Serializing checks prevents parallel guesses bypassing the persisted attempt budget.
        with self.lock, self.db.session() as db:
            now = time.time()
            db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < now - 60))
            count = db.scalar(select(func.count()).select_from(LoginAttempt)) or 0
            if count >= 8:
                db.commit()
                raise ApiError(
                    429, "LOGIN_THROTTLED", "Wait a minute before signing in again.", True
                )
            db.add(LoginAttempt(attempted_at=now))
            db.commit()
            owner = db.get(Owner, "owner")
            password_hash = owner.password_hash if owner else DUMMY_HASH
            valid: bool
            try:
                valid = hasher.verify(password_hash, credentials.password.get_secret_value())
            except (VerificationError, InvalidHashError):
                valid = False
            if not valid or not owner or credentials.login_name != owner.login_name:
                raise ApiError(401, "INVALID_LOGIN", "The username or password is incorrect.")
        return self.issue_session()

    def issue_session(self) -> str:
        token = secrets.token_urlsafe(32)
        with self.db.session() as db:
            db.execute(delete(Session).where(Session.expires_at <= time.time()))
            db.add(
                Session(
                    id_hash=digest(token),
                    user_id="owner",
                    csrf_hash=digest(csrf_for(token)),
                    expires_at=time.time() + SESSION_SECONDS,
                )
            )
            db.commit()
        return token

    def require(self, request: Request, *, csrf: bool = False) -> SessionView:
        token = request.cookies.get(COOKIE, "")
        with self.db.session() as db:
            session = db.get(Session, digest(token)) if token else None
            if session is None or session.expires_at <= time.time():
                raise ApiError(401, "SIGN_IN_REQUIRED", "Sign in to Porchlight.")
            if csrf and not secrets.compare_digest(
                digest(request.headers.get("x-csrf-token", "")), session.csrf_hash
            ):
                raise ApiError(403, "CSRF_REQUIRED", "Refresh the page before making this change.")
            owner = db.get(Owner, session.user_id)
            if owner is None:
                raise ApiError(401, "SIGN_IN_REQUIRED", "Sign in to Porchlight.")
            return SessionView(login_name=owner.login_name, csrf_token=csrf_for(token))

    def logout(self, request: Request) -> None:
        with self.db.session() as db:
            db.execute(
                delete(Session).where(Session.id_hash == digest(request.cookies.get(COOKIE, "")))
            )
            db.commit()

    def session_valid(self, actor: str) -> bool:
        with self.db.session() as db:
            row = db.get(Session, actor)
            return row is not None and row.expires_at > time.time()
