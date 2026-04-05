from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any, Literal, Protocol

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import HHBrowserConnection
from app.schemas.hh_browser_integration import HHBrowserConnectionDebug, HHBrowserConnectionSummary
from app.services.hh_action_control_service import HHActionControlService
from app.services.hh_automation_diagnostics_service import diagnostic_for_code
from app.services.hh_browser_error_taxonomy import normalize_automation_error_code
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
HHSessionValidationOutcome = Literal["valid", "expired", "logged_out", "invalid_storage", "network/transient_failure"]

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

_RETRYABLE_AUTOMATION_CODES = {"transient_navigation", "transient_wait"}
_TRANSIENT_VALIDATION_CODES = {"transient_navigation", "transient_wait", "network_error"}
_USER_ERROR_MESSAGES: dict[str, str] = {
    "playwright_unavailable": "Browser automation runtime is unavailable.",
    "transient_navigation": "HH login page is temporarily unavailable. Retry in a moment.",
    "transient_wait": "HH login step timed out. Retry in a moment.",
    "session_persist_failed": "Unable to persist HH session. Restart connect flow.",
    "page_not_recognized": "Unable to continue HH login flow. Restart connect flow.",
}


class HHBrowserAutomationError(Exception):
    def __init__(self, code: str, message: str, *, debug_summary: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = normalize_automation_error_code(code)
        self.message = message
        self.debug_summary = debug_summary or {}


class HHLoginPageAdapter(Protocol):
    def open_login_page(self) -> HHLoginStep: ...

    def submit_identifier(self, *, identifier: str, identifier_type: Literal["phone", "email"]) -> HHLoginStep: ...

    def submit_password(self, *, password: str) -> HHLoginStep: ...

    def submit_code(self, *, code: str) -> HHLoginStep: ...

    def export_storage_state(self) -> dict: ...

    def safe_debug_summary(self) -> dict[str, Any]: ...

    def close(self) -> None: ...


class HHAdapterFactory(Protocol):
    def create(self) -> HHLoginPageAdapter: ...


class HHSessionStorage(Protocol):
    def save(self, *, user_id: int, connection_id: int, state: dict) -> str: ...

    def load(self, *, ref: str) -> dict: ...

    def delete(self, *, ref: str) -> None: ...


class HHSessionProbeAdapter(Protocol):
    def check_authenticated(self) -> bool: ...

    def close(self) -> None: ...


class HHSessionProbeFactory(Protocol):
    def create(self, *, storage_state: dict) -> HHSessionProbeAdapter: ...


@dataclass(slots=True)
class RuntimeSession:
    runtime_session_id: str
    connection_id: int
    user_id: int
    adapter: HHLoginPageAdapter
    created_at: datetime
    last_seen_at: datetime
    last_detected_step: HHLoginStep | None = None


@dataclass(slots=True)
class HHSessionValidationResult:
    outcome: HHSessionValidationOutcome
    error_code: str | None = None
    error_message: str | None = None
    clear_session_ref: bool = False
    detected_session_expires_at: datetime | None = None


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
        configured = base_dir or os.getenv("HH_BROWSER_SESSION_DIR", "/tmp/job-search-app/hh_browser_sessions")
        self.base_dir = Path(configured).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.base_dir, 0o700)
        except OSError:
            logger.warning("HH session dir permission hardening failed for path=%s", redact_text(str(self.base_dir), max_len=80))

    def save(self, *, user_id: int, connection_id: int, state: dict) -> str:
        _ = user_id
        _ = connection_id
        state_id = uuid.uuid4().hex
        filename = f"session_{state_id}.json"
        filepath = self.base_dir / filename
        payload = json.dumps(state, ensure_ascii=False)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.base_dir, delete=False) as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        try:
            os.chmod(tmp_path, 0o600)
            tmp_path.replace(filepath)
            os.chmod(filepath, 0o600)
        except OSError:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise
        return f"local://hh-browser-session/{filename}"

    def load(self, *, ref: str) -> dict:
        filepath = self._resolve_ref(ref)
        return json.loads(filepath.read_text(encoding="utf-8"))

    def delete(self, *, ref: str) -> None:
        filepath = self._resolve_ref(ref)
        if filepath.exists():
            filepath.unlink()

    def _resolve_ref(self, ref: str) -> Path:
        prefix = "local://hh-browser-session/"
        if not ref.startswith(prefix):
            raise ValueError("Unsupported session reference format")
        filename = ref.replace(prefix, "", 1)
        if not filename or "/" in filename or ".." in filename:
            raise ValueError("Invalid session reference path")
        resolved = (self.base_dir / filename).resolve()
        if resolved.parent != self.base_dir:
            raise ValueError("Invalid session reference path")
        return resolved


class HHBrowserConnectService:
    def __init__(
        self,
        db: Session,
        *,
        adapter_factory: HHAdapterFactory,
        runtime_registry: InMemoryRuntimeRegistry,
        session_storage: HHSessionStorage,
        session_probe_factory: HHSessionProbeFactory | None = None,
    ) -> None:
        self.db = db
        self.adapter_factory = adapter_factory
        self.runtime_registry = runtime_registry
        self.session_storage = session_storage
        self.session_probe_factory = session_probe_factory
        self.action_control = HHActionControlService(db)

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
        action_decision = self.action_control.start_action(
            user_id=user_id,
            action_type="connect",
            target_type="browser_connection",
            target_id=user_id,
            target_ref="hh",
            request_fingerprint=f"connect:{user_id}:{int(force_restart)}",
            min_interval_seconds=2,
            max_concurrent_per_user=2,
        )

        self._transition(connection, "connecting")
        connection.last_error_code = None
        connection.last_error_message = None
        connection.last_checked_at = self._now()
        self.db.commit()

        started_at = time.perf_counter()
        adapter: HHLoginPageAdapter | None = None
        try:
            adapter = self.adapter_factory.create()
            next_step = self._run_with_retry(lambda: adapter.open_login_page(), operation="open_login_page")
            runtime = RuntimeSession(
                runtime_session_id=uuid.uuid4().hex,
                connection_id=connection.id,
                user_id=user_id,
                adapter=adapter,
                created_at=self._now(),
                last_seen_at=self._now(),
                last_detected_step=next_step,
            )
            self.runtime_registry.put(runtime)
            self._apply_step(connection, next_step)
            self.db.commit()
            self._log_transition(
                event="start",
                connection=connection,
                runtime_session_id=runtime.runtime_session_id,
                detected_step=next_step,
                elapsed_ms=int((time.perf_counter() - started_at) * 1000),
            )
            self.action_control.finish_action(
                action_run=action_decision.action_run,
                status_value="completed",
                operation_code="HH_CONNECT_STARTED",
                safe_summary=f"HH connect flow started and moved to step={next_step}",
                context_ref={"connection_id": connection.id},
            )
            return self._summary(connection)
        except HHBrowserAutomationError as exc:
            if adapter is not None and self.runtime_registry.get(connection.id) is None:
                adapter.close()
            self._mark_failed(connection, error_code=exc.code, error_message=exc.message, debug_summary=exc.debug_summary)
            self.action_control.finish_action(
                action_run=action_decision.action_run,
                status_value="retryable_failed" if exc.code in _RETRYABLE_AUTOMATION_CODES else "failed",
                operation_code="HH_CONNECT_FAILED",
                safe_summary=f"HH connect flow failed with code={exc.code[:32]}",
                context_ref={"connection_id": connection.id},
            )
            self._raise_user_automation_error(exc)

    def submit_identifier(self, *, user_id: int, identifier: str, identifier_type: Literal["phone", "email"]) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._ensure_state(connection, expected="awaiting_identifier")
        runtime = self._runtime_or_fail(connection)
        started_at = time.perf_counter()
        try:
            next_step = self._run_with_retry(
                lambda: runtime.adapter.submit_identifier(identifier=identifier, identifier_type=identifier_type),
                operation="submit_identifier",
            )
            runtime.last_detected_step = next_step
            self._apply_step(connection, next_step)
            self.db.commit()
            self._log_transition(
                event="submit_identifier",
                connection=connection,
                runtime_session_id=runtime.runtime_session_id,
                detected_step=next_step,
                elapsed_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return self._summary(connection)
        except HHBrowserAutomationError as exc:
            self._mark_failed(connection, error_code=exc.code, error_message=exc.message, debug_summary=exc.debug_summary)
            self._raise_user_automation_error(exc)

    def submit_password(self, *, user_id: int, password: str) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._ensure_state(connection, expected="awaiting_password")
        runtime = self._runtime_or_fail(connection)
        started_at = time.perf_counter()
        try:
            next_step = self._run_with_retry(lambda: runtime.adapter.submit_password(password=password), operation="submit_password")
            runtime.last_detected_step = next_step
            self._apply_step(connection, next_step)
            self.db.commit()
            self._log_transition(
                event="submit_password",
                connection=connection,
                runtime_session_id=runtime.runtime_session_id,
                detected_step=next_step,
                elapsed_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return self._summary(connection)
        except HHBrowserAutomationError as exc:
            self._mark_failed(connection, error_code=exc.code, error_message=exc.message, debug_summary=exc.debug_summary)
            self._raise_user_automation_error(exc)

    def submit_code(self, *, user_id: int, code: str) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._ensure_state(connection, expected="awaiting_code")
        runtime = self._runtime_or_fail(connection)
        started_at = time.perf_counter()
        try:
            next_step = self._run_with_retry(lambda: runtime.adapter.submit_code(code=code), operation="submit_code")
            runtime.last_detected_step = next_step
            self._apply_step(connection, next_step)
            self.db.commit()
            self._log_transition(
                event="submit_code",
                connection=connection,
                runtime_session_id=runtime.runtime_session_id,
                detected_step=next_step,
                elapsed_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return self._summary(connection)
        except HHBrowserAutomationError as exc:
            self._mark_failed(connection, error_code=exc.code, error_message=exc.message, debug_summary=exc.debug_summary)
            self._raise_user_automation_error(exc)

    def cancel(self, *, user_id: int) -> HHBrowserConnectionSummary:
        action_decision = self.action_control.start_action(
            user_id=user_id,
            action_type="connect_cancel",
            target_type="browser_connection",
            target_id=user_id,
            target_ref="hh",
            request_fingerprint=f"connect_cancel:{user_id}",
            min_interval_seconds=1,
            max_concurrent_per_user=3,
        )
        connection = self._ensure_connection(user_id=user_id)
        self._close_runtime(connection.id)
        if connection.session_state_ref:
            self._delete_session_state(connection.session_state_ref)
        self._transition(connection, "disconnected")
        connection.requires_reauth = False
        connection.last_checked_at = self._now()
        connection.session_state_ref = None
        connection.session_expires_at = None
        connection.last_error_code = None
        connection.last_error_message = None
        self.db.commit()
        self._log_transition(event="cancel", connection=connection, runtime_session_id=None, detected_step=None, elapsed_ms=0)
        self.action_control.finish_action(
            action_run=action_decision.action_run,
            status_value="cancelled",
            operation_code="HH_ACTION_CANCELLED",
            safe_summary="HH connect runtime/session was cancelled manually",
            context_ref={"connection_id": connection.id},
        )
        return self._summary(connection)

    def restore_session(self, *, user_id: int) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        result = self._validate_stored_session(connection=connection)
        self._apply_lifecycle_policy(connection=connection, result=result, event="restore_session")
        self.db.commit()
        self._log_transition(
            event="restore_session",
            connection=connection,
            runtime_session_id=None,
            detected_step=("connected" if result.outcome == "valid" else "failed"),
            elapsed_ms=0,
        )
        return self._summary(connection)

    def check_session(self, *, user_id: int) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        result = self._validate_stored_session(connection=connection)
        self._apply_lifecycle_policy(connection=connection, result=result, event="check_session")
        self.db.commit()
        self._log_transition(
            event="check_session",
            connection=connection,
            runtime_session_id=None,
            detected_step=None,
            elapsed_ms=0,
        )
        return self._summary(connection)

    def validate_session(self, *, user_id: int) -> dict[str, Any]:
        connection = self._ensure_connection(user_id=user_id)
        result = self._validate_stored_session(connection=connection)
        self._apply_lifecycle_policy(connection=connection, result=result, event="validate_session")
        self.db.commit()
        summary = self._summary(connection)
        return {
            "outcome": result.outcome,
            "status": summary.status,
            "requires_reauth": summary.requires_reauth,
            "last_checked_at": summary.last_checked_at,
            "session_present": summary.session_present,
            "last_error_code": summary.last_error_code,
            "last_error_message": summary.last_error_message,
        }

    def refresh_session_status(self, *, user_id: int) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        result = self._validate_stored_session(connection=connection)
        self._apply_lifecycle_policy(connection=connection, result=result, event="refresh_session_status")
        self.db.commit()
        return self._summary(connection)

    def require_reauth(self, *, user_id: int) -> HHBrowserConnectionSummary:
        connection = self._ensure_connection(user_id=user_id)
        self._transition(connection, "requires_reauth")
        connection.requires_reauth = True
        connection.last_checked_at = self._now()
        connection.last_error_code = "reauth_required_manual"
        connection.last_error_message = "Manual reauthentication requested"
        self.db.commit()
        return self._summary(connection)

    def _run_with_retry(self, callback, *, operation: str) -> HHLoginStep:
        attempts = 2
        for attempt in range(1, attempts + 1):
            try:
                return callback()
            except HHBrowserAutomationError as exc:
                if exc.code not in _RETRYABLE_AUTOMATION_CODES or attempt >= attempts:
                    raise
                logger.warning("HH transient failure | operation=%s attempt=%s code=%s", operation, attempt, exc.code)
        raise HHBrowserAutomationError("transient_wait", "Retry budget exhausted")

    def _apply_step(self, connection: HHBrowserConnection, step: HHLoginStep) -> None:
        if step == "connected":
            runtime = self._runtime_or_fail(connection)
            session_state = self._sanitize_storage_state(runtime.adapter.export_storage_state())
            previous_session_ref = connection.session_state_ref
            try:
                session_ref = self.session_storage.save(user_id=connection.user_id, connection_id=connection.id, state=session_state)
            except (OSError, ValueError) as exc:
                raise HHBrowserAutomationError("session_persist_failed", "Unable to store HH session state") from exc
            self._transition(connection, "connected")
            connection.session_state_ref = session_ref
            connection.last_authenticated_at = self._now()
            connection.last_checked_at = connection.last_authenticated_at
            connection.session_expires_at = self._detect_session_expiry(session_state)
            connection.requires_reauth = False
            connection.last_error_code = None
            connection.last_error_message = None
            self._close_runtime(connection.id)
            if previous_session_ref and previous_session_ref != session_ref:
                self._delete_session_state(previous_session_ref)
            return

        if step == "failed":
            runtime = self.runtime_registry.get(connection.id)
            debug_summary = runtime.adapter.safe_debug_summary() if runtime is not None else {}
            self._mark_failed(
                connection,
                error_code="page_not_recognized",
                error_message="Unable to determine HH login step",
                debug_summary=debug_summary,
            )
            return

        self._transition(connection, step)
        connection.last_checked_at = self._now()

    def _mark_failed(
        self,
        connection: HHBrowserConnection,
        *,
        error_code: str,
        error_message: str,
        debug_summary: dict[str, Any] | None = None,
    ) -> None:
        self._transition(connection, "failed")
        connection.requires_reauth = False
        connection.last_checked_at = self._now()
        connection.last_error_code = redact_text(normalize_automation_error_code(error_code), max_len=64)
        connection.last_error_message = redact_text(error_message, max_len=160)
        self._close_runtime(connection.id)
        self.db.commit()
        logger.warning(
            "HH connect failed | user_id=%s connection_id=%s code=%s reason=%s next_step=%s message=%s debug=%s",
            connection.user_id,
            connection.id,
            connection.last_error_code,
            diagnostic_for_code(connection.last_error_code).reason,
            diagnostic_for_code(connection.last_error_code).guidance,
            connection.last_error_message,
            self._sanitize_debug(debug_summary or {}),
        )

    def _runtime_or_fail(self, connection: HHBrowserConnection) -> RuntimeSession:
        runtime = self.runtime_registry.get(connection.id)
        if runtime is None:
            self._mark_failed(connection, error_code="session_timeout", error_message="Live browser session expired")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "session_timeout", "message": "Live browser session expired, restart connect flow"},
            )
        return runtime

    def _expire_stale_runtime(self, connection: HHBrowserConnection) -> None:
        runtime = self.runtime_registry.get(connection.id)
        if runtime is None and connection.status in {"connecting", "awaiting_identifier", "awaiting_password", "awaiting_code"}:
            self._mark_failed(connection, error_code="session_timeout", error_message="Live browser session expired")

    def _close_runtime(self, connection_id: int) -> None:
        runtime = self.runtime_registry.pop(connection_id)
        if runtime is not None:
            runtime.adapter.close()

    def _validate_stored_session(self, *, connection: HHBrowserConnection) -> HHSessionValidationResult:
        now = self._now()
        if self.session_probe_factory is None:
            return HHSessionValidationResult(
                outcome="network/transient_failure",
                error_code="SESSION_PROBE_UNAVAILABLE",
                error_message="Session probe adapter is not configured",
            )

        if not connection.session_state_ref:
            return HHSessionValidationResult(
                outcome="invalid_storage",
                error_code="session_state_missing",
                error_message="No persisted HH browser session",
            )

        if connection.session_expires_at and connection.session_expires_at <= now:
            return HHSessionValidationResult(
                outcome="expired",
                error_code="session_expired",
                error_message="Persisted HH browser session reached cookie expiry",
                clear_session_ref=True,
            )

        try:
            storage_state = self.session_storage.load(ref=connection.session_state_ref)
        except FileNotFoundError:
            return HHSessionValidationResult(
                outcome="invalid_storage",
                error_code="session_state_not_found",
                error_message="Persisted HH browser session was not found",
                clear_session_ref=True,
            )
        except (json.JSONDecodeError, ValueError, OSError):
            return HHSessionValidationResult(
                outcome="invalid_storage",
                error_code="session_state_corrupted",
                error_message="Persisted HH browser session is corrupted",
                clear_session_ref=True,
            )

        detected_expiry = self._detect_session_expiry(storage_state)
        if detected_expiry and detected_expiry <= now:
            return HHSessionValidationResult(
                outcome="expired",
                error_code="session_expired",
                error_message="Persisted HH browser session reached cookie expiry",
                clear_session_ref=True,
                detected_session_expires_at=detected_expiry,
            )

        try:
            probe = self.session_probe_factory.create(storage_state=storage_state)
            try:
                is_authenticated = probe.check_authenticated()
            finally:
                probe.close()
        except HHBrowserAutomationError as exc:
            outcome: HHSessionValidationOutcome = "network/transient_failure"
            return HHSessionValidationResult(
                outcome=outcome,
                error_code=exc.code,
                error_message=exc.message,
                clear_session_ref=False,
            )

        if is_authenticated:
            return HHSessionValidationResult(
                outcome="valid",
                detected_session_expires_at=detected_expiry,
            )

        return HHSessionValidationResult(
            outcome="logged_out",
            error_code="session_logged_out",
            error_message="Stored HH session is no longer authenticated",
            clear_session_ref=True,
            detected_session_expires_at=detected_expiry,
        )

    def _apply_lifecycle_policy(
        self,
        *,
        connection: HHBrowserConnection,
        result: HHSessionValidationResult,
        event: str,
    ) -> None:
        now = self._now()
        connection.last_checked_at = now
        if result.detected_session_expires_at is not None:
            connection.session_expires_at = result.detected_session_expires_at

        if result.outcome == "valid":
            self._transition(connection, "connected")
            connection.requires_reauth = False
            connection.last_authenticated_at = now
            connection.last_error_code = None
            connection.last_error_message = None
            if event == "restore_session":
                logger.info("HH session restored | user_id=%s connection_id=%s", connection.user_id, connection.id)
            return

        if result.outcome in {"expired", "logged_out"}:
            self._transition(connection, "requires_reauth")
            connection.requires_reauth = True
            connection.last_error_code = redact_text(result.error_code or "session_reauth_required", max_len=64)
            connection.last_error_message = redact_text(result.error_message or "HH reauthentication is required", max_len=160)
            if result.clear_session_ref and connection.session_state_ref:
                self._delete_session_state(connection.session_state_ref)
                connection.session_state_ref = None
                connection.session_expires_at = None
            logger.warning(
                "hh_session_requires_reauth user_id=%s connection_id=%s outcome=%s code=%s reason=%s",
                connection.user_id,
                connection.id,
                result.outcome,
                connection.last_error_code,
                diagnostic_for_code(connection.last_error_code).reason,
            )
            return

        if result.outcome == "invalid_storage":
            target_status: HHConnectStatus = "disconnected" if result.error_code == "session_state_missing" else "requires_reauth"
            self._transition(connection, target_status)
            connection.requires_reauth = target_status == "requires_reauth"
            connection.last_error_code = redact_text(result.error_code or "session_state_invalid", max_len=64)
            connection.last_error_message = redact_text(result.error_message or "Persisted HH session state is invalid", max_len=160)
            if result.clear_session_ref and connection.session_state_ref:
                self._delete_session_state(connection.session_state_ref)
                connection.session_state_ref = None
                connection.session_expires_at = None
            return

        self._transition(connection, "failed")
        connection.requires_reauth = False
        connection.last_error_code = redact_text(result.error_code or "session_validation_failed", max_len=64)
        connection.last_error_message = redact_text(result.error_message or "Transient failure during HH session validation", max_len=160)

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
        runtime = self.runtime_registry.get(connection.id)
        debug = HHBrowserConnectionDebug(
            current_detected_step=(runtime.last_detected_step if runtime is not None else None),
            last_transition_at=connection.updated_at,
            runtime_session_alive=runtime is not None,
        )
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
                "debug": debug,
            }
        )

    def _log_transition(
        self,
        *,
        event: str,
        connection: HHBrowserConnection,
        runtime_session_id: str | None,
        detected_step: HHLoginStep | None,
        elapsed_ms: int,
    ) -> None:
        logger.info(
            "HH connect transition | event=%s user_id=%s connection_id=%s runtime_session_id=%s status=%s detected_step=%s elapsed_ms=%s",
            event,
            connection.user_id,
            connection.id,
            runtime_session_id,
            connection.status,
            detected_step,
            elapsed_ms,
        )

    @staticmethod
    def _sanitize_debug(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            redact_text(str(key), max_len=64): redact_text(str(value), max_len=160)
            for key, value in payload.items()
            if key not in {"html", "dom", "cookies", "storage"}
        }

    @staticmethod
    def _sanitize_storage_state(state: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        if isinstance(state.get("cookies"), list):
            sanitized["cookies"] = state["cookies"]
        if isinstance(state.get("origins"), list):
            sanitized["origins"] = state["origins"]
        return sanitized

    @staticmethod
    def _detect_session_expiry(state: dict[str, Any]) -> datetime | None:
        cookies = state.get("cookies")
        if not isinstance(cookies, list):
            return None
        expiries: list[float] = []
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            value = cookie.get("expires")
            if isinstance(value, (int, float)) and value > 0:
                expiries.append(float(value))
        if not expiries:
            return None
        return datetime.fromtimestamp(min(expiries), tz=timezone.utc)

    def _delete_session_state(self, ref: str) -> None:
        try:
            self.session_storage.delete(ref=ref)
        except (OSError, ValueError):
            logger.warning("Unable to delete HH session state file for ref=%s", redact_text(ref, max_len=80))

    def _raise_user_automation_error(self, exc: HHBrowserAutomationError) -> None:
        message = _USER_ERROR_MESSAGES.get(exc.code, "HH automation step failed. Restart connect flow.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": message},
        ) from exc

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
