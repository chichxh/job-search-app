from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import HHBrowserConnection, HHManagedResume
from app.services.hh_action_control_service import HHActionControlService
from app.services.hh_automation_diagnostics_service import diagnostic_for_code
from app.services.hh_browser_error_taxonomy import normalize_automation_error_code

logger = logging.getLogger(__name__)

HH_VISIBILITY_MODES = (
    "public_default",
    "hidden_from_all",
    "visible_selected_employers",
    "unknown",
    "change_pending",
    "change_failed",
)
HH_VISIBILITY_STATUSES = ("idle", "checking", "check_failed", "change_pending", "change_failed", "updated", "inferred_post_apply")


class HHResumeVisibilityAutomationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = normalize_automation_error_code(code)
        self.message = message


@dataclass(slots=True)
class HHResumeVisibilityResult:
    current_visibility_mode: str
    checked_at: datetime


@dataclass(slots=True)
class HHResumeVisibilityChangeResult:
    current_visibility_mode: str
    checked_at: datetime
    changed_at: datetime


class HHResumeVisibilityAutomationClient(Protocol):
    def detect_visibility(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        managed_resume: HHManagedResume,
    ) -> HHResumeVisibilityResult: ...

    def hide_from_all(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        managed_resume: HHManagedResume,
    ) -> HHResumeVisibilityChangeResult: ...


class HHResumeVisibilityAutomationClientStub:
    def detect_visibility(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        managed_resume: HHManagedResume,
    ) -> HHResumeVisibilityResult:
        raise HHResumeVisibilityAutomationError(
            code="AUTOMATION_NOT_IMPLEMENTED",
            message="HH resume visibility automation is not implemented in this build",
        )

    def hide_from_all(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        managed_resume: HHManagedResume,
    ) -> HHResumeVisibilityChangeResult:
        raise HHResumeVisibilityAutomationError(
            code="AUTOMATION_NOT_IMPLEMENTED",
            message="HH resume visibility automation is not implemented in this build",
        )


class HHResumeVisibilityService:
    def __init__(
        self,
        db: Session,
        *,
        automation_client: HHResumeVisibilityAutomationClient,
    ) -> None:
        self.db = db
        self.automation_client = automation_client
        self.action_control = HHActionControlService(db)

    def get_visibility(self, *, user_id: int, managed_resume_id: int) -> HHManagedResume:
        return self._owned_resume(user_id=user_id, managed_resume_id=managed_resume_id)

    def check_visibility(self, *, user_id: int, managed_resume_id: int) -> HHManagedResume:
        action_decision = self.action_control.start_action(
            user_id=user_id,
            action_type="check_visibility",
            target_type="managed_resume",
            target_id=managed_resume_id,
            target_ref=None,
            request_fingerprint=f"check_visibility:{user_id}:{managed_resume_id}",
            min_interval_seconds=2,
            max_concurrent_per_user=2,
        )
        try:
            managed = self._owned_resume(user_id=user_id, managed_resume_id=managed_resume_id)
            connection = self._require_active_session(user_id=user_id)
            started = time.perf_counter()

            managed.visibility_status = "checking"
            managed.visibility_error_code = None
            managed.visibility_error_message = None
            self.db.commit()

            try:
                result = self.automation_client.detect_visibility(
                    user_id=user_id,
                    connection=connection,
                    managed_resume=managed,
                )
            except HHResumeVisibilityAutomationError as exc:
                managed.visibility_status = "check_failed"
                managed.current_visibility_mode = "change_failed"
                managed.visibility_error_code = exc.code[:64]
                managed.visibility_error_message = "Unable to check HH resume visibility. Reconnect and retry."
                self.db.commit()
                self.db.refresh(managed)
                self.action_control.finish_action(
                    action_run=action_decision.action_run,
                    status_value="retryable_failed",
                    operation_code="HH_VISIBILITY_CHECK_FAILED",
                    safe_summary=f"Visibility check failed with code={exc.code[:32]}",
                    context_ref={"managed_resume_id": managed.id},
                )
                diag = diagnostic_for_code(exc.code)
                logger.warning(
                    "hh_resume_visibility_check_failed user_id=%s managed_resume_id=%s code=%s reason=%s next_step=%s duration_ms=%s",
                    user_id,
                    managed.id,
                    exc.code[:64],
                    diag.reason,
                    diag.guidance,
                    int((time.perf_counter() - started) * 1000),
                )
                return managed

            managed.current_visibility_mode = self._validated_mode(result.current_visibility_mode)
            managed.visibility_last_checked_at = result.checked_at
            managed.visibility_status = "updated"
            managed.visibility_error_code = None
            managed.visibility_error_message = None
            self.db.commit()
            self.db.refresh(managed)
            self.action_control.finish_action(
                action_run=action_decision.action_run,
                status_value="completed",
                operation_code="HH_VISIBILITY_CHECK_COMPLETED",
                safe_summary=f"Visibility check completed with mode={managed.current_visibility_mode}",
                context_ref={"managed_resume_id": managed.id},
            )
            logger.info(
                "hh_resume_visibility_checked user_id=%s managed_resume_id=%s mode=%s duration_ms=%s",
                user_id,
                managed.id,
                managed.current_visibility_mode,
                int((time.perf_counter() - started) * 1000),
            )
            return managed
        except HTTPException:
            self.action_control.finish_action(
                action_run=action_decision.action_run,
                status_value="failed",
                operation_code="HH_VISIBILITY_CHECK_REJECTED",
                safe_summary="Visibility check rejected by policy guard",
            )
            raise

    def hide_from_all(self, *, user_id: int, managed_resume_id: int) -> HHManagedResume:
        action_decision = self.action_control.start_action(
            user_id=user_id,
            action_type="hide_visibility",
            target_type="managed_resume",
            target_id=managed_resume_id,
            target_ref="hidden_from_all",
            request_fingerprint=f"hide_visibility:{user_id}:{managed_resume_id}:hidden_from_all",
            min_interval_seconds=3,
            max_concurrent_per_user=2,
        )
        try:
            managed = self._owned_resume(user_id=user_id, managed_resume_id=managed_resume_id)
            connection = self._require_active_session(user_id=user_id)
            started = time.perf_counter()
            if (
                managed.current_visibility_mode == "hidden_from_all"
                and managed.visibility_status == "updated"
                and managed.visibility_last_changed_at is not None
            ):
                self.action_control.finish_action(
                    action_run=action_decision.action_run,
                    status_value="completed",
                    operation_code="HH_DUPLICATE_PREVENTED",
                    safe_summary="Visibility hide action skipped: resume is already hidden from all",
                    context_ref={"managed_resume_id": managed.id},
                )
                return managed

            managed.desired_visibility_mode = "hidden_from_all"
            managed.visibility_status = "change_pending"
            managed.current_visibility_mode = "change_pending"
            managed.visibility_error_code = None
            managed.visibility_error_message = None
            self.db.commit()

            try:
                result = self.automation_client.hide_from_all(
                    user_id=user_id,
                    connection=connection,
                    managed_resume=managed,
                )
            except HHResumeVisibilityAutomationError as exc:
                managed.visibility_status = "change_failed"
                managed.current_visibility_mode = "change_failed"
                managed.visibility_error_code = exc.code[:64]
                managed.visibility_error_message = "Unable to change HH resume visibility. Reconnect and retry."
                self.db.commit()
                self.db.refresh(managed)
                self.action_control.finish_action(
                    action_run=action_decision.action_run,
                    status_value="retryable_failed",
                    operation_code="HH_VISIBILITY_HIDE_FAILED",
                    safe_summary=f"Visibility hide failed with code={exc.code[:32]}",
                    context_ref={"managed_resume_id": managed.id},
                )
                diag = diagnostic_for_code(exc.code)
                logger.warning(
                    "hh_resume_visibility_hide_failed user_id=%s managed_resume_id=%s code=%s reason=%s next_step=%s duration_ms=%s",
                    user_id,
                    managed.id,
                    exc.code[:64],
                    diag.reason,
                    diag.guidance,
                    int((time.perf_counter() - started) * 1000),
                )
                return managed

            managed.current_visibility_mode = self._validated_mode(result.current_visibility_mode)
            managed.visibility_last_checked_at = result.checked_at
            managed.visibility_last_changed_at = result.changed_at
            managed.visibility_status = "updated"
            managed.visibility_error_code = None
            managed.visibility_error_message = None
            self.db.commit()
            self.db.refresh(managed)
            self.action_control.finish_action(
                action_run=action_decision.action_run,
                status_value="completed",
                operation_code="HH_VISIBILITY_HIDE_COMPLETED",
                safe_summary="Visibility changed to hidden_from_all",
                context_ref={"managed_resume_id": managed.id},
            )
            logger.info(
                "hh_resume_visibility_hidden user_id=%s managed_resume_id=%s mode=%s duration_ms=%s",
                user_id,
                managed.id,
                managed.current_visibility_mode,
                int((time.perf_counter() - started) * 1000),
            )
            return managed
        except HTTPException:
            self.action_control.finish_action(
                action_run=action_decision.action_run,
                status_value="failed",
                operation_code="HH_VISIBILITY_HIDE_REJECTED",
                safe_summary="Visibility hide request rejected by policy guard",
            )
            raise

    def _validated_mode(self, value: str) -> str:
        return value if value in HH_VISIBILITY_MODES else "unknown"

    def _owned_resume(self, *, user_id: int, managed_resume_id: int) -> HHManagedResume:
        managed = self.db.get(HHManagedResume, managed_resume_id)
        if managed is None or managed.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        if not managed.hh_resume_external_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Managed resume is not linked to HH resume yet",
            )
        return managed

    def _require_active_session(self, *, user_id: int) -> HHBrowserConnection:
        items = self.db.query(HHBrowserConnection).all()
        connection = next((item for item in items if item.user_id == user_id), None)
        if connection is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active HH browser session required")
        if connection.status != "connected" or not connection.session_state_ref or connection.requires_reauth:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active HH browser session required")
        return connection
