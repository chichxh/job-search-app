from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    CoverLetterVersion,
    HHApplyRun,
    HHBrowserConnection,
    HHManagedResume,
    Profile,
    Vacancy,
)
from app.schemas.hh_browser_integration import HHApplyRequest
from app.services.hh_apply_application_sync_service import HHApplyApplicationSyncService

logger = logging.getLogger(__name__)

_SAFE_VISIBILITY_FOR_APPLY = {"hidden_from_all", "public_default", "unknown"}


class HHApplyAutomationError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False, response_ref: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.response_ref = response_ref or {}


@dataclass(slots=True)
class HHApplyAutomationResult:
    result_type: str
    result_message: str
    response_ref: dict[str, Any] | None = None


class HHApplyAutomationClient(Protocol):
    def apply_to_vacancy(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        apply_run: HHApplyRun,
        managed_resume: HHManagedResume,
        vacancy: Vacancy,
        cover_letter_text: str | None,
        dry_run: bool,
    ) -> HHApplyAutomationResult: ...


class HHApplyAutomationClientStub:
    def apply_to_vacancy(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        apply_run: HHApplyRun,
        managed_resume: HHManagedResume,
        vacancy: Vacancy,
        cover_letter_text: str | None,
        dry_run: bool,
    ) -> HHApplyAutomationResult:
        if dry_run:
            return HHApplyAutomationResult(
                result_type="dry_run",
                result_message="Apply flow validated locally; browser submit is skipped",
                response_ref={"dry_run": True, "resume_external_id_present": bool(managed_resume.hh_resume_external_id)},
            )
        raise HHApplyAutomationError(
            code="AUTOMATION_NOT_IMPLEMENTED",
            message="HH browser apply automation is not implemented in this build",
            retryable=True,
        )


class HHApplyService:
    def __init__(
        self,
        db: Session,
        *,
        automation_client: HHApplyAutomationClient,
        sync_service: HHApplyApplicationSyncService | None = None,
    ) -> None:
        self.db = db
        self.automation_client = automation_client
        self.sync_service = sync_service or HHApplyApplicationSyncService(db)

    def apply(self, *, user_id: int, request: HHApplyRequest) -> HHApplyRun:
        started_perf = time.perf_counter()
        connection = self._require_active_session(user_id=user_id)
        vacancy = self._require_vacancy(request.vacancy_id)
        managed_resume = self._require_managed_resume(
            user_id=user_id,
            managed_resume_id=request.hh_resume_managed_id,
        )
        profile = self._require_owned_profile(user_id=user_id, profile_id=managed_resume.profile_id)

        cover_letter = self._resolve_cover_letter_version(
            user_id=user_id,
            profile_id=profile.id,
            cover_letter_version_id=request.cover_letter_version_id,
        )
        cover_letter_text = self._resolve_cover_letter_text(request=request, cover_letter=cover_letter)

        if request.force_visibility_check:
            self._apply_visibility_policy(managed_resume=managed_resume)

        apply_run = HHApplyRun(
            user_id=user_id,
            profile_id=profile.id,
            vacancy_id=vacancy.id,
            hh_resume_managed_id=managed_resume.id,
            source_cover_letter_version_id=cover_letter.id if cover_letter else None,
            status="queued",
            hh_vacancy_url=vacancy.url,
            started_at=self._now(),
        )
        self.db.add(apply_run)
        self.db.commit()
        self.db.refresh(apply_run)

        try:
            self._set_status(apply_run, "opening_vacancy")
            self._set_status(apply_run, "awaiting_resume_selection")
            if cover_letter_text:
                self._set_status(apply_run, "awaiting_cover_letter")
            self._set_status(apply_run, "submitting")

            result = self.automation_client.apply_to_vacancy(
                user_id=user_id,
                connection=connection,
                apply_run=apply_run,
                managed_resume=managed_resume,
                vacancy=vacancy,
                cover_letter_text=cover_letter_text,
                dry_run=request.dry_run,
            )

            apply_run.status = "already_applied" if result.result_type == "already_applied" else "submitted"
            apply_run.result_type = result.result_type[:64]
            apply_run.result_message = (result.result_message or "Apply completed")[:160]
            apply_run.hh_response_ref = self._safe_response_ref(result.response_ref)
            apply_run.finished_at = self._now()
            self.db.commit()
            self.db.refresh(apply_run)
            self._sync_to_local_application(apply_run)
            logger.info(
                "hh_apply_run_submitted user_id=%s vacancy_id=%s hh_resume_managed_id=%s apply_run_id=%s result_type=%s duration_ms=%s",
                user_id,
                vacancy.id,
                managed_resume.id,
                apply_run.id,
                apply_run.result_type,
                int((time.perf_counter() - started_perf) * 1000),
            )
            return apply_run
        except HHApplyAutomationError as exc:
            apply_run.status = "retryable_failed" if exc.retryable else "failed"
            apply_run.result_type = exc.code[:64]
            apply_run.result_message = "Unable to submit HH apply flow. Reconnect and retry."[:160]
            apply_run.hh_response_ref = self._safe_response_ref(exc.response_ref)
            apply_run.finished_at = self._now()
            self.db.commit()
            self.db.refresh(apply_run)
            self._sync_to_local_application(apply_run)
            logger.warning(
                "hh_apply_run_failed user_id=%s vacancy_id=%s hh_resume_managed_id=%s apply_run_id=%s result_type=%s duration_ms=%s",
                user_id,
                vacancy.id,
                managed_resume.id,
                apply_run.id,
                apply_run.result_type,
                int((time.perf_counter() - started_perf) * 1000),
            )
            return apply_run

    def list_runs(self, *, user_id: int) -> list[HHApplyRun]:
        items = self.db.query(HHApplyRun).all()
        owned = [item for item in items if item.user_id == user_id]
        return sorted(owned, key=lambda item: (item.started_at, item.id), reverse=True)

    def get_run(self, *, user_id: int, apply_run_id: int) -> HHApplyRun:
        item = self.db.get(HHApplyRun, apply_run_id)
        if item is None or item.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return item

    def sync_run_to_application(self, *, user_id: int, apply_run_id: int):
        run = self.get_run(user_id=user_id, apply_run_id=apply_run_id)
        return self.sync_service.sync_apply_run(apply_run=run)

    def _resolve_cover_letter_text(self, *, request: HHApplyRequest, cover_letter: CoverLetterVersion | None) -> str | None:
        if request.cover_letter_text is not None:
            return request.cover_letter_text.strip()
        if cover_letter is None:
            return None
        text = (cover_letter.content_text or "").strip()
        return text or None

    def _require_active_session(self, *, user_id: int) -> HHBrowserConnection:
        connection = next((item for item in self.db.query(HHBrowserConnection).all() if item.user_id == user_id), None)
        if connection is None or connection.status != "connected" or connection.requires_reauth or not connection.session_state_ref:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "HH_SESSION_REQUIRED", "message": "Active HH browser session required"},
            )
        return connection

    def _require_vacancy(self, vacancy_id: int) -> Vacancy:
        vacancy = self.db.get(Vacancy, vacancy_id)
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "VACANCY_NOT_FOUND", "message": "Vacancy not found"},
            )
        return vacancy

    def _require_managed_resume(self, *, user_id: int, managed_resume_id: int) -> HHManagedResume:
        managed_resume = self.db.get(HHManagedResume, managed_resume_id)
        if managed_resume is None or managed_resume.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        if not managed_resume.hh_resume_external_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "HH_RESUME_EXTERNAL_REF_MISSING", "message": "Managed resume is not linked to HH resume yet"},
            )
        return managed_resume

    def _require_owned_profile(self, *, user_id: int, profile_id: int) -> Profile:
        profile = self.db.get(Profile, profile_id)
        if profile is None or profile.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return profile

    def _resolve_cover_letter_version(
        self,
        *,
        user_id: int,
        profile_id: int,
        cover_letter_version_id: int | None,
    ) -> CoverLetterVersion | None:
        if cover_letter_version_id is None:
            return None
        item = self.db.get(CoverLetterVersion, cover_letter_version_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "COVER_LETTER_NOT_FOUND", "message": "Cover letter version not found"},
            )
        owner_profile = self.db.get(Profile, item.profile_id)
        if owner_profile is None or owner_profile.user_id != user_id or item.profile_id != profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return item

    def _apply_visibility_policy(self, *, managed_resume: HHManagedResume) -> None:
        if managed_resume.current_visibility_mode in _SAFE_VISIBILITY_FOR_APPLY:
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "VISIBILITY_CONFIRMATION_REQUIRED",
                "message": "Resume visibility requires confirmation before apply",
            },
        )

    def _set_status(self, apply_run: HHApplyRun, next_status: str) -> None:
        apply_run.status = next_status
        self.db.commit()

    def _safe_response_ref(self, response_ref: dict[str, Any] | None) -> dict[str, Any] | None:
        if not response_ref:
            return None
        safe: dict[str, Any] = {}
        for key in (
            "hh_response_type",
            "hh_apply_id",
            "dry_run",
            "resume_external_id_present",
            "vacancy_url",
            "applied_at",
            "confirmation_summary",
        ):
            if key in response_ref:
                safe[key] = response_ref[key]
        return safe or None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _sync_to_local_application(self, apply_run: HHApplyRun) -> None:
        try:
            self.sync_service.sync_apply_run(apply_run=apply_run)
        except Exception:  # noqa: BLE001
            logger.exception(
                "hh_apply_sync_failed apply_run_id=%s profile_id=%s vacancy_id=%s",
                apply_run.id,
                apply_run.profile_id,
                apply_run.vacancy_id,
            )
