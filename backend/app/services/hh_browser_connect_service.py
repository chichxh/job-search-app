from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal, Protocol

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import HHBrowserConnection
from app.schemas.hh_browser_integration import HHBrowserConnectionSummary
from app.utils.log_safety import redact_text

logger = logging.getLogger(__name__)

HHConnectStatus = Literal[
    "disconnected",
    "connecting",
    "awaiting_identifier",
    "awaiting_password",
    "awaiting_code",
    "connected",
    "requires_reauth",
    "failed",
]

HHLoginStep = Literal["awaiting_identifier", "awaiting_password", "awaiting_code", "connected", "failed"]

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "disconnected": {"connecting"},
    "connecting": {"awaiting_identifier", "awaiting_password", "awaiting_code", "connected", "failed", "disconnected"},
    "awaiting_identifier": {"awaiting_password", "awaiting_code", "connected", "failed", "disconnected"},
    "awaiting_password": {"awaiting_code", "connected", "failed", "disconnected"},
    "awaiting_code": {"connected", "failed", "disconnected"},
    "connected": {"requires_reauth", "failed", "disconnected"},
    "requires_reauth": {"connecting", "disconnected", "failed"},
    "failed": {"connecting", "disconnected"},
}


class HHBrowserAutomationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class HHLoginPageAdapter(Protocol):
    def open_login_page(self) -> HHLoginStep: ...

    def submit_identifier(self, *, identifier: str, identifier_type: Literal["phone", "email"]) -> HHLoginStep: ...

    def submit_password(self, *, password: str) -> HHLoginStep: ...

    def submit_code(self, *, code: str) -> HHLoginStep: ...

    def export_storage_state(self) -> dict: ...

    def close(self) -> None: ...


class HHAdapterFactory(Protocol):
    def create(self) -> HHLoginPageAdapter: ...


class HHSessionStorage(Protocol):
    def save(self, *, user_id: int, connection_id: int, state: dict) -> str: ...


@dataclass(slots=True)
class RuntimeSession:
    connection_id: int
    user_id: int
    adapter: HHLoginPageAdapter
    created_at: datetime
    last_seen_at: datetime


class InMemoryRuntimeRegistry:
    def __init__(self, timeout_seconds: int = 600) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = Lock()
        self._by_connection: dict[int, RuntimeSession] = {}

    def put(self, runtime: RuntimeSession) -> None:
        with self._lock:
            self._by_connection[runtime.connection_id] = runtime

    def get(self, connection_id: int) -> RuntimeSession | None:
        with self._lock:
            runtime = self._by_connection.get(connection_id)
            if runtime is None:
                return None
            elapsed = (datetime.now(timezone.utc) - runtime.last_seen_at).total_seconds()
            if elapsed > self.timeout_seconds:
                self._by_connection.pop(connection_id, None)
                runtime.adapter.close()
                return None
            runtime.last_seen_at = datetime.now(timezone.utc)
            return runtime

    def pop(self, connection_id: int) -> RuntimeSession | None:
        with self._lock:
            return self._by_connection.pop(connection_id, None)


class LocalSessionStorage:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or os.getenv("HH_BROWSER_SESSION_DIR", "/tmp/hh_browser_sessions"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, *, user_id: int, connection_id: int, state: dict) -> str:
        state_id = uuid.uuid4().hex
        filepath = self.base_dir / f"u{user_id}_c{connection_id}_{state_id}.json"
        filepath.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        return f"local://hh-browser-session/{filepath.name}"


class HHBrowserConnectService:
    def __init__(
        self,
        db: Session,
        *,
        adapter_factory: HHAdapterFactory,
        runtime_registry: InMemoryRuntimeRegistry,
        session_storage: HHSessionStorage,
    ) -> None:
        self.db = db
        self.adapter_factory = adapter_factory
        self.runtime_registry = runtime_registry
        self.session_storage = session_storage

    def get_state(self, *, user_id: int) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._expire_stale_runtime(connection)
        return self._summary(connection)

    def start(self, *, user_id: int, force_restart: bool = False) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        runtime = self.runtime_registry.get(connection.id)
        if runtime is not None and not force_restart:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connect flow already active")

        if runtime is not None:
            self._close_runtime(connection.id)

        self._transition(connection, "connecting")
        connection.last_error_code = None
        connection.last_error_message = None
        connection.last_checked_at = self._now()
        self.db.commit()

        start_ts = time.perf_counter()
        try:
            adapter = self.adapter_factory.create()
            next_step = adapter.open_login_page()
            runtime = RuntimeSession(
                connection_id=connection.id,
                user_id=user_id,
                adapter=adapter,
                created_at=self._now(),
                last_seen_at=self._now(),
            )
            self.runtime_registry.put(runtime)
            self._apply_step(connection, next_step)
            self.db.commit()
            logger.info(
                "HH connect started | user_id=%s connection_id=%s step=%s elapsed_ms=%s",
                user_id,
                connection.id,
                next_step,
                int((time.perf_counter() - start_ts) * 1000),
            )
            return self._summary(connection)
        except HHBrowserAutomationError as exc:
            self._mark_failed(connection, error_code=exc.code, error_message=exc.message)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": exc.message}) from exc

    def submit_identifier(self, *, user_id: int, identifier: str, identifier_type: Literal["phone", "email"]) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._ensure_state(connection, expected="awaiting_identifier")
        runtime = self._runtime_or_fail(connection.id)
        try:
            next_step = runtime.adapter.submit_identifier(identifier=identifier, identifier_type=identifier_type)
            self._apply_step(connection, next_step)
            self.db.commit()
            logger.info(
                "HH identifier submitted | user_id=%s connection_id=%s type=%s step=%s",
                user_id,
                connection.id,
                identifier_type,
                next_step,
            )
            return self._summary(connection)
        except HHBrowserAutomationError as exc:
            self._mark_failed(connection, error_code=exc.code, error_message=exc.message)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": exc.message}) from exc

    def submit_password(self, *, user_id: int, password: str) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._ensure_state(connection, expected="awaiting_password")
        runtime = self._runtime_or_fail(connection.id)
        try:
            next_step = runtime.adapter.submit_password(password=password)
            self._apply_step(connection, next_step)
            self.db.commit()
            logger.info("HH password submitted | user_id=%s connection_id=%s step=%s", user_id, connection.id, next_step)
            return self._summary(connection)
        except HHBrowserAutomationError as exc:
            self._mark_failed(connection, error_code=exc.code, error_message=exc.message)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": exc.message}) from exc

    def submit_code(self, *, user_id: int, code: str) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._ensure_state(connection, expected="awaiting_code")
        runtime = self._runtime_or_fail(connection.id)
        try:
            next_step = runtime.adapter.submit_code(code=code)
            self._apply_step(connection, next_step)
            self.db.commit()
            logger.info("HH OTP submitted | user_id=%s connection_id=%s step=%s", user_id, connection.id, next_step)
            return self._summary(connection)
        except HHBrowserAutomationError as exc:
            self._mark_failed(connection, error_code=exc.code, error_message=exc.message)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": exc.message}) from exc

    def cancel(self, *, user_id: int) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._close_runtime(connection.id)
        self._transition(connection, "disconnected")
        connection.requires_reauth = False
        connection.last_checked_at = self._now()
        connection.last_error_code = None
        connection.last_error_message = None
        self.db.commit()
        logger.info("HH connect cancelled | user_id=%s connection_id=%s", user_id, connection.id)
        return self._summary(connection)

    def _apply_step(self, connection: HHBrowserConnection, step: HHLoginStep) -> None:
        if step == "connected":
            runtime = self._runtime_or_fail(connection.id)
            session_state = runtime.adapter.export_storage_state()
            session_ref = self.session_storage.save(user_id=connection.user_id, connection_id=connection.id, state=session_state)
            self._transition(connection, "connected")
            connection.session_state_ref = session_ref
            connection.last_authenticated_at = self._now()
            connection.last_checked_at = connection.last_authenticated_at
            connection.requires_reauth = False
            connection.last_error_code = None
            connection.last_error_message = None
            self._close_runtime(connection.id)
            return

        if step == "failed":
            self._mark_failed(connection, error_code="UNRECOGNIZED_STATE", error_message="Unable to determine HH login step")
            return

        self._transition(connection, step)
        connection.last_checked_at = self._now()

    def _mark_failed(self, connection: HHBrowserConnection, *, error_code: str, error_message: str) -> None:
        self._transition(connection, "failed")
        connection.requires_reauth = False
        connection.last_checked_at = self._now()
        connection.last_error_code = redact_text(error_code, max_len=64)
        connection.last_error_message = redact_text(error_message, max_len=160)
        self._close_runtime(connection.id)
        self.db.commit()
        logger.warning(
            "HH connect failed | user_id=%s connection_id=%s code=%s message=%s",
            connection.user_id,
            connection.id,
            connection.last_error_code,
            connection.last_error_message,
        )

    def _runtime_or_fail(self, connection_id: int) -> RuntimeSession:
        runtime = self.runtime_registry.get(connection_id)
        if runtime is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SESSION_TIMEOUT", "message": "Live browser session expired, restart connect flow"},
            )
        return runtime

    def _expire_stale_runtime(self, connection: HHBrowserConnection) -> None:
        runtime = self.runtime_registry.get(connection.id)
        if runtime is None and connection.status in {"connecting", "awaiting_identifier", "awaiting_password", "awaiting_code"}:
            self._mark_failed(connection, error_code="SESSION_TIMEOUT", error_message="Live browser session expired")

    def _close_runtime(self, connection_id: int) -> None:
        runtime = self.runtime_registry.pop(connection_id)
        if runtime is not None:
            runtime.adapter.close()

    def _ensure_connection(self, *, user_id: int) -> HHBrowserConnection:
        connection = next((item for item in self.db.query(HHBrowserConnection).all() if item.user_id == user_id), None)
        if connection is None:
            connection = HHBrowserConnection(user_id=user_id, status="disconnected", requires_reauth=False)
            self.db.add(connection)
            self.db.commit()
            self.db.refresh(connection)
        return connection

    def _ensure_state(self, connection: HHBrowserConnection, *, expected: HHConnectStatus) -> None:
        if connection.status != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TRANSITION", "message": f"Expected state {expected}, got {connection.status}"},
            )

    def _transition(self, connection: HHBrowserConnection, next_status: HHConnectStatus) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(connection.status, set())
        if next_status != connection.status and next_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TRANSITION", "message": f"Cannot transition {connection.status} -> {next_status}"},
            )
        connection.status = next_status
        connection.updated_at = self._now()

    def _summary(self, connection: HHBrowserConnection) -> HHBrowserConnectionSummary:
        return HHBrowserConnectionSummary.model_validate(
            {
                "status": connection.status,
                "requires_reauth": bool(connection.requires_reauth),
                "last_authenticated_at": connection.last_authenticated_at,
                "last_checked_at": connection.last_checked_at,
                "session_present": bool(connection.session_state_ref),
                "last_error_code": connection.last_error_code,
                "last_error_message": connection.last_error_message,
                "updated_at": connection.updated_at,
            }
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
