from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from sqlalchemy.orm import Session

from app.db.models import Application, ApplicationStatusHistory, HHApplyRun, HHManagedResume

_SYNCABLE_APPLY_STATUSES = {"submitted", "already_applied"}
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HHApplySyncResult:
    apply_run_id: int
    synced: bool
    reason: str
    application: Application | None = None
    history_entry: ApplicationStatusHistory | None = None
    action: str | None = None


class HHApplyApplicationSyncService:
    """Sync HH apply run outcomes into local applications funnel.

    Policy (MVP):
    - submitted/already_applied:
      * upsert application by (profile_id, vacancy_id)
      * set local status=applied
      * link documents and HH artifacts
      * write application_status_history once per hh_apply_run_id (idempotent)
    - failed/retryable_failed/other:
      * do not move local status to applied
      * return no-op
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def sync_apply_run(self, *, apply_run: HHApplyRun) -> HHApplySyncResult:
        if apply_run.status not in _SYNCABLE_APPLY_STATUSES:
            return HHApplySyncResult(
                apply_run_id=apply_run.id,
                synced=False,
                reason=f"apply_run_status_{apply_run.status}_not_syncable",
            )

        application = self._find_application(profile_id=apply_run.profile_id, vacancy_id=apply_run.vacancy_id)
        created = application is None
        action = "created_application" if created else "updated_existing_application"
        if application is None:
            application = Application(
                profile_id=apply_run.profile_id,
                vacancy_id=apply_run.vacancy_id,
                status="applied",
            )
            self.db.add(application)
            self.db.commit()
            self.db.refresh(application)

        previous_status = None if created else application.status
        managed_resume = self.db.get(HHManagedResume, apply_run.hh_resume_managed_id)
        application.status = "applied"
        application.resume_version_id = managed_resume.source_resume_version_id if managed_resume else application.resume_version_id
        application.cover_letter_version_id = apply_run.source_cover_letter_version_id
        application.last_hh_apply_run_id = apply_run.id
        application.hh_managed_resume_id = apply_run.hh_resume_managed_id
        application.external_apply_status = apply_run.status
        application.last_external_apply_at = self._resolve_external_apply_at(apply_run=apply_run)
        application.updated_at = self._now()
        self.db.commit()
        self.db.refresh(application)

        history_entry = self._ensure_history_entry(
            application=application,
            apply_run=apply_run,
            previous_status=previous_status,
            created=created,
        )

        if history_entry is None:
            action = "skipped_duplicate_sync"

        logger.info(
            "hh_apply_sync_decision apply_run_id=%s application_id=%s action=%s external_apply_status=%s",
            apply_run.id,
            application.id,
            action,
            apply_run.status,
        )

        return HHApplySyncResult(
            apply_run_id=apply_run.id,
            synced=True,
            reason="already_applied_mapped" if apply_run.status == "already_applied" else "synced",
            application=application,
            history_entry=history_entry,
            action=action,
        )

    def _ensure_history_entry(
        self,
        *,
        application: Application,
        apply_run: HHApplyRun,
        previous_status: str,
        created: bool,
    ) -> ApplicationStatusHistory | None:
        existing = next(
            (
                item
                for item in self.db.query(ApplicationStatusHistory).all()
                if item.hh_apply_run_id == apply_run.id
            ),
            None,
        )
        if existing is not None:
            return existing

        if previous_status == "applied" and not created:
            return None

        note = (
            "Synced from HH apply run: already_applied"
            if apply_run.status == "already_applied"
            else "Synced from HH apply run: submitted"
        )
        history = ApplicationStatusHistory(
            application_id=application.id,
            from_status=None if created else previous_status,
            to_status="applied",
            note=note,
            hh_apply_run_id=apply_run.id,
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def _find_application(self, *, profile_id: int, vacancy_id: int) -> Application | None:
        return next(
            (
                item
                for item in self.db.query(Application).all()
                if item.profile_id == profile_id and item.vacancy_id == vacancy_id
            ),
            None,
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _resolve_external_apply_at(self, *, apply_run: HHApplyRun) -> datetime:
        if apply_run.hh_response_ref and isinstance(apply_run.hh_response_ref.get("applied_at"), str):
            raw = apply_run.hh_response_ref["applied_at"]
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                pass
        return apply_run.finished_at or self._now()
