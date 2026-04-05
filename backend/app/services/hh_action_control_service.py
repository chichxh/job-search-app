from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import HHAutomationActionRun

IN_PROGRESS_ACTION_STATUSES = {"running"}
TERMINAL_ACTION_STATUSES = {
    "completed",
    "failed",
    "retryable_failed",
    "duplicate_prevented",
    "retry_skipped",
    "conflict_detected",
    "rate_limited",
    "cancelled",
}


@dataclass(slots=True)
class HHActionStartDecision:
    action_run: HHAutomationActionRun
    reused_context: dict[str, Any] | None = None


class HHActionControlService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start_action(
        self,
        *,
        user_id: int,
        action_type: str,
        target_type: str,
        target_id: int | None,
        target_ref: str | None,
        request_fingerprint: str,
        min_interval_seconds: int = 2,
        max_concurrent_per_user: int = 3,
    ) -> HHActionStartDecision:
        now = self._now()

        running_for_user = [
            item
            for item in self.db.query(HHAutomationActionRun).all()
            if item.user_id == user_id and item.status in IN_PROGRESS_ACTION_STATUSES
        ]
        if len(running_for_user) >= max_concurrent_per_user:
            run = self._create_run(
                user_id=user_id,
                action_type=action_type,
                target_type=target_type,
                target_id=target_id,
                target_ref=target_ref,
                request_fingerprint=request_fingerprint,
                status="rate_limited",
                operation_code="HH_ACTION_RATE_LIMITED",
                safe_summary="Too many active HH automation actions for user",
                started_at=now,
                finished_at=now,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "HH_ACTION_RATE_LIMITED", "message": "Too many active HH automation actions"},
            )

        latest_same_request = next(
            (
                item
                for item in sorted(
                    self.db.query(HHAutomationActionRun).all(),
                    key=lambda r: (r.started_at, r.id),
                    reverse=True,
                )
                if item.user_id == user_id and item.action_type == action_type and item.request_fingerprint == request_fingerprint
            ),
            None,
        )
        conflicting = next(
            (
                item
                for item in self.db.query(HHAutomationActionRun).all()
                if item.user_id == user_id
                and item.action_type == action_type
                and item.target_type == target_type
                and item.target_id == target_id
                and item.status in IN_PROGRESS_ACTION_STATUSES
            ),
            None,
        )
        if conflicting is not None:
            self._create_run(
                user_id=user_id,
                action_type=action_type,
                target_type=target_type,
                target_id=target_id,
                target_ref=target_ref,
                request_fingerprint=request_fingerprint,
                status="conflict_detected",
                operation_code="HH_ACTION_CONFLICT_DETECTED",
                safe_summary="Conflicting HH action is already running for target",
                started_at=now,
                finished_at=now,
                parent_action_id=conflicting.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "HH_ACTION_CONFLICT_DETECTED", "message": "Conflicting HH action is already running"},
            )

        completed_same_request = next(
            (
                item
                for item in sorted(
                    self.db.query(HHAutomationActionRun).all(),
                    key=lambda r: (r.started_at, r.id),
                    reverse=True,
                )
                if item.user_id == user_id
                and item.action_type == action_type
                and item.request_fingerprint == request_fingerprint
                and item.status == "completed"
            ),
            None,
        )
        if completed_same_request is not None:
            run = self._create_run(
                user_id=user_id,
                action_type=action_type,
                target_type=target_type,
                target_id=target_id,
                target_ref=target_ref,
                request_fingerprint=request_fingerprint,
                status="duplicate_prevented",
                operation_code="HH_DUPLICATE_PREVENTED",
                safe_summary="Duplicate HH action request skipped due to completed result",
                started_at=now,
                finished_at=now,
                retry_of_action_id=completed_same_request.id,
                parent_action_id=completed_same_request.id,
                context_ref=completed_same_request.context_ref,
            )
            return HHActionStartDecision(action_run=run, reused_context=completed_same_request.context_ref or None)

        retry_from = next(
            (
                item
                for item in sorted(
                    self.db.query(HHAutomationActionRun).all(),
                    key=lambda r: (r.started_at, r.id),
                    reverse=True,
                )
                if item.user_id == user_id
                and item.action_type == action_type
                and item.request_fingerprint == request_fingerprint
                and item.status in {"retryable_failed", "failed"}
            ),
            None,
        )
        if retry_from is not None and retry_from.status == "failed":
            self._create_run(
                user_id=user_id,
                action_type=action_type,
                target_type=target_type,
                target_id=target_id,
                target_ref=target_ref,
                request_fingerprint=request_fingerprint,
                status="retry_skipped",
                operation_code="HH_RETRY_SKIPPED_TERMINAL",
                safe_summary="Retry skipped because previous action failed terminally",
                started_at=now,
                finished_at=now,
                retry_of_action_id=retry_from.id,
                parent_action_id=retry_from.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "HH_RETRY_SKIPPED_TERMINAL", "message": "Previous HH action failed terminally"},
            )

        if (
            latest_same_request is not None
            and latest_same_request.started_at >= now - timedelta(seconds=min_interval_seconds)
            and latest_same_request.status in {"running", "rate_limited", "conflict_detected"}
        ):
            self._create_run(
                user_id=user_id,
                action_type=action_type,
                target_type=target_type,
                target_id=target_id,
                target_ref=target_ref,
                request_fingerprint=request_fingerprint,
                status="rate_limited",
                operation_code="HH_ACTION_SPAM_PREVENTED",
                safe_summary="Rapid duplicate request was throttled",
                started_at=now,
                finished_at=now,
                parent_action_id=latest_same_request.id,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "HH_ACTION_SPAM_PREVENTED", "message": "Please wait before retrying this HH action"},
            )

        run = self._create_run(
            user_id=user_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            target_ref=target_ref,
            request_fingerprint=request_fingerprint,
            status="running",
            operation_code="HH_ACTION_STARTED",
            safe_summary="HH automation action started",
            started_at=now,
            retry_of_action_id=retry_from.id if retry_from and retry_from.status == "retryable_failed" else None,
            parent_action_id=retry_from.id if retry_from and retry_from.status == "retryable_failed" else None,
        )
        return HHActionStartDecision(action_run=run)

    def finish_action(
        self,
        *,
        action_run: HHAutomationActionRun,
        status_value: str,
        operation_code: str,
        safe_summary: str,
        context_ref: dict[str, Any] | None = None,
    ) -> HHAutomationActionRun:
        action_run.status = status_value
        action_run.operation_code = operation_code[:64]
        action_run.safe_summary = safe_summary[:200]
        if context_ref is not None:
            action_run.context_ref = context_ref
        action_run.finished_at = self._now()
        self.db.commit()
        self.db.refresh(action_run)
        return action_run

    def request_cancel(self, *, user_id: int, action_run_id: int) -> HHAutomationActionRun:
        action_run = self.db.get(HHAutomationActionRun, action_run_id)
        if action_run is None or action_run.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        if action_run.status in TERMINAL_ACTION_STATUSES:
            return action_run
        action_run.cancel_requested = True
        action_run.operation_code = "HH_ACTION_CANCEL_REQUESTED"
        action_run.safe_summary = "Cancel requested for running HH automation action"
        self.db.commit()
        self.db.refresh(action_run)
        return action_run

    def _create_run(
        self,
        *,
        user_id: int,
        action_type: str,
        target_type: str,
        target_id: int | None,
        target_ref: str | None,
        request_fingerprint: str,
        status: str,
        operation_code: str,
        safe_summary: str,
        started_at: datetime,
        finished_at: datetime | None = None,
        retry_of_action_id: int | None = None,
        parent_action_id: int | None = None,
        context_ref: dict[str, Any] | None = None,
    ) -> HHAutomationActionRun:
        run = HHAutomationActionRun(
            user_id=user_id,
            action_type=action_type[:64],
            target_type=target_type[:64],
            target_id=target_id,
            target_ref=(target_ref or "")[:160] or None,
            request_fingerprint=request_fingerprint[:160],
            status=status[:32],
            operation_code=operation_code[:64],
            safe_summary=safe_summary[:200],
            retry_of_action_id=retry_of_action_id,
            parent_action_id=parent_action_id,
            started_at=started_at,
            finished_at=finished_at,
            context_ref=context_ref,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
