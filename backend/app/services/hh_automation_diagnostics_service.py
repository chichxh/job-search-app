from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import HHAutomationActionRun, HHBrowserConnection, HHManagedResume
from app.services.hh_browser_error_taxonomy import normalize_automation_error_code

_RECENT_FAILURE_STATUSES = {"failed", "retryable_failed", "conflict_detected", "rate_limited", "retry_skipped"}


@dataclass(slots=True)
class HHFailureDiagnostic:
    reason: str
    guidance: str


_FAILURE_DIAGNOSTIC_MAP: dict[str, HHFailureDiagnostic] = {
    "session_expired": HHFailureDiagnostic(
        reason="session_expired",
        guidance="Reconnect HH browser session and re-run the action.",
    ),
    "session_timeout": HHFailureDiagnostic(
        reason="runtime_session_expired",
        guidance="Restart connect flow because runtime browser session timed out.",
    ),
    "page_not_recognized": HHFailureDiagnostic(
        reason="login_step_not_recognized",
        guidance="Inspect HH login page object selectors and restart connect flow.",
    ),
    "selector_not_found": HHFailureDiagnostic(
        reason="selector_not_found",
        guidance="Inspect selector/page object layer for recent HH UI changes.",
    ),
    "resume_surface_not_available": HHFailureDiagnostic(
        reason="resume_constructor_surface_unavailable",
        guidance="Open HH resume constructor manually and verify constructor step support.",
    ),
    "apply_surface_not_available": HHFailureDiagnostic(
        reason="apply_surface_unavailable",
        guidance="Open vacancy apply page manually; retry after HH UI/apply controls are available.",
    ),
    "vacancy_page_unavailable": HHFailureDiagnostic(
        reason="vacancy_page_unavailable",
        guidance="Vacancy is likely archived/unavailable on HH. Skip and choose another vacancy.",
    ),
    "response_unavailable": HHFailureDiagnostic(
        reason="response_unavailable",
        guidance="HH currently does not accept responses for this vacancy.",
    ),
    "apply_entry_not_found": HHFailureDiagnostic(
        reason="apply_entry_not_found",
        guidance="Apply button/link was not detected on vacancy page. Verify current HH layout.",
    ),
    "target_resume_not_selectable": HHFailureDiagnostic(
        reason="resume_selection_mismatch",
        guidance="Could not deterministically map managed resume to HH selection options.",
    ),
    "cover_letter_required": HHFailureDiagnostic(
        reason="cover_letter_required",
        guidance="Provide a cover letter text and retry.",
    ),
    "already_applied": HHFailureDiagnostic(
        reason="already_applied",
        guidance="No retry needed; ensure local applications funnel was synced.",
    ),
    "resume_selection_mismatch": HHFailureDiagnostic(
        reason="resume_selection_mismatch",
        guidance="Verify chosen managed resume matches HH vacancy apply selector.",
    ),
    "visibility_controls_not_found": HHFailureDiagnostic(
        reason="visibility_controls_not_found",
        guidance="Inspect resume visibility selectors/page object layer and retry.",
    ),
}


def diagnostic_for_code(code: str | None) -> HHFailureDiagnostic:
    if not code:
        return HHFailureDiagnostic(reason="unknown", guidance="Inspect safe logs and retry if transient.")
    normalized = normalize_automation_error_code(code)
    return _FAILURE_DIAGNOSTIC_MAP.get(
        normalized,
        _FAILURE_DIAGNOSTIC_MAP.get(
            code,
            HHFailureDiagnostic(reason=f"error_code:{normalized}", guidance="Inspect safe logs and runbook; retry if transient."),
        ),
    )


class HHAutomationDiagnosticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_summary(self, *, user_id: int, recent_limit: int = 10, failure_limit: int = 5) -> dict[str, Any]:
        connection = next((item for item in self.db.query(HHBrowserConnection).all() if item.user_id == user_id), None)
        action_runs = [item for item in self.db.query(HHAutomationActionRun).all() if item.user_id == user_id]
        managed_resumes = [item for item in self.db.query(HHManagedResume).all() if item.user_id == user_id]

        ordered_actions = sorted(action_runs, key=lambda item: (item.started_at, item.id), reverse=True)
        recent_actions = ordered_actions[: max(recent_limit, 0)]
        recent_failures = [item for item in ordered_actions if item.status in _RECENT_FAILURE_STATUSES][: max(failure_limit, 0)]

        error_distribution: dict[str, int] = {}
        for item in recent_failures:
            key = (item.operation_code or "unknown")[:64]
            error_distribution[key] = error_distribution.get(key, 0) + 1

        last_action = ordered_actions[0] if ordered_actions else None
        runtime_signal = {
            "playwright_available": self._playwright_available(),
            "runtime_registry": "in_memory",
        }

        return {
            "generated_at": self._now(),
            "connection": {
                "status": connection.status if connection else "disconnected",
                "requires_reauth": bool(connection.requires_reauth) if connection else False,
                "session_present": bool(connection.session_state_ref) if connection else False,
                "session_expires_at": connection.session_expires_at if connection else None,
                "last_checked_at": connection.last_checked_at if connection else None,
                "last_authenticated_at": connection.last_authenticated_at if connection else None,
                "last_error_code": connection.last_error_code if connection else None,
                "last_error_message": connection.last_error_message if connection else None,
                "runtime_session_alive": bool(connection and connection.status in {"connecting", "awaiting_identifier", "awaiting_password", "awaiting_code"}),
            },
            "managed_resumes": {
                "total": len(managed_resumes),
                "creating": len([item for item in managed_resumes if item.status == "creating"]),
                "failed": len([item for item in managed_resumes if item.status == "failed"]),
                "visibility_change_failed": len([item for item in managed_resumes if item.visibility_status == "change_failed"]),
            },
            "last_action": self._serialize_action(last_action),
            "recent_failures": [self._serialize_action(item, include_guidance=True) for item in recent_failures],
            "failure_distribution": error_distribution,
            "runtime": runtime_signal,
        }

    def list_recent_actions(self, *, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        action_runs = [item for item in self.db.query(HHAutomationActionRun).all() if item.user_id == user_id]
        ordered = sorted(action_runs, key=lambda item: (item.started_at, item.id), reverse=True)
        return [self._serialize_action(item, include_guidance=True) for item in ordered[: max(limit, 0)]]

    def _serialize_action(self, item: HHAutomationActionRun | None, *, include_guidance: bool = False) -> dict[str, Any] | None:
        if item is None:
            return None
        data: dict[str, Any] = {
            "action_run_id": item.id,
            "action_type": item.action_type,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "status": item.status,
            "operation_code": item.operation_code,
            "safe_summary": item.safe_summary,
            "cancel_requested": bool(item.cancel_requested),
            "started_at": item.started_at or self._now(),
            "finished_at": item.finished_at,
        }
        if include_guidance:
            diag = diagnostic_for_code(self._error_code_for_action(item))
            data["diagnostic_reason"] = diag.reason
            data["recommended_next_step"] = diag.guidance
        return data

    def _error_code_for_action(self, item: HHAutomationActionRun) -> str | None:
        if item.safe_summary and "code=" in item.safe_summary:
            _, _, tail = item.safe_summary.partition("code=")
            return tail.split()[0][:64]
        return item.operation_code

    def _playwright_available(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401

            return True
        except Exception:
            return False

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
