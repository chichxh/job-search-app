from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Callable

from app.db.models import HHBrowserConnection, HHManagedResume
from app.services.hh_browser_connect_service import LocalSessionStorage
from app.services.hh_browser_page_objects import HHNavigationHelper
from app.services.hh_browser_playwright import PlaywrightBrowserRuntime
from app.services.hh_resume_visibility_service import (
    HHResumeVisibilityAutomationError,
    HHResumeVisibilityChangeResult,
    HHResumeVisibilityResult,
)

logger = logging.getLogger(__name__)


class PlaywrightResumeVisibilityAutomationClient:
    def __init__(
        self,
        *,
        session_storage: LocalSessionStorage | None = None,
        runtime_factory: Callable[[dict], PlaywrightBrowserRuntime] | None = None,
    ) -> None:
        self.session_storage = session_storage or LocalSessionStorage()
        self.runtime_factory = runtime_factory or (lambda state: PlaywrightBrowserRuntime(storage_state=state))

    def detect_visibility(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        managed_resume: HHManagedResume,
    ) -> HHResumeVisibilityResult:
        runtime, nav = self._open_runtime(connection=connection)
        try:
            self._open_visibility_controls(nav=nav, managed_resume=managed_resume)
            current_mode = nav.resumes_page.detect_visibility_mode()
            if current_mode == "unknown":
                logger.info("hh_resume_visibility_unknown user_id=%s managed_resume_id=%s", user_id, managed_resume.id)
            return HHResumeVisibilityResult(current_visibility_mode=current_mode, checked_at=datetime.now(timezone.utc))
        finally:
            runtime.close()

    def hide_from_all(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        managed_resume: HHManagedResume,
    ) -> HHResumeVisibilityChangeResult:
        return self.ensure_resume_hidden_from_all(user_id=user_id, connection=connection, managed_resume=managed_resume)

    def ensure_resume_hidden_from_all(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        managed_resume: HHManagedResume,
    ) -> HHResumeVisibilityChangeResult:
        runtime, nav = self._open_runtime(connection=connection)
        try:
            self._open_visibility_controls(nav=nav, managed_resume=managed_resume)
            current_mode = nav.resumes_page.detect_visibility_mode()
            changed_at = datetime.now(timezone.utc)
            if current_mode == "hidden_from_all":
                return HHResumeVisibilityChangeResult(
                    current_visibility_mode=current_mode,
                    checked_at=changed_at,
                    changed_at=changed_at,
                )
            if current_mode == "unknown":
                raise HHResumeVisibilityAutomationError(
                    code="VISIBILITY_UNKNOWN_LAYOUT",
                    message="Unable to determine current resume visibility mode",
                )

            if not nav.resumes_page.select_hide_from_all():
                raise HHResumeVisibilityAutomationError(
                    code="VISIBILITY_HIDE_OPTION_UNAVAILABLE",
                    message="Hide-from-all option is unavailable in current HH layout",
                )
            if not nav.resumes_page.save_visibility():
                raise HHResumeVisibilityAutomationError(
                    code="VISIBILITY_SAVE_NOT_FOUND",
                    message="Unable to find visibility save/apply action",
                )

            current_mode = nav.resumes_page.detect_visibility_mode()
            success = nav.resumes_page.visibility_success_detected() or current_mode == "hidden_from_all"
            if not success:
                raise HHResumeVisibilityAutomationError(
                    code="VISIBILITY_POST_SAVE_VERIFY_FAILED",
                    message="Visibility update could not be verified after save",
                )
            if current_mode == "unknown":
                current_mode = "hidden_from_all"

            return HHResumeVisibilityChangeResult(
                current_visibility_mode=current_mode,
                checked_at=changed_at,
                changed_at=changed_at,
            )
        finally:
            runtime.close()

    def _open_runtime(self, *, connection: HHBrowserConnection) -> tuple[PlaywrightBrowserRuntime, HHNavigationHelper]:
        if not connection.session_state_ref:
            raise HHResumeVisibilityAutomationError(code="AUTH_SESSION_MISSING", message="Active HH session state is missing")

        try:
            storage_state = self.session_storage.load(ref=connection.session_state_ref)
        except Exception as exc:  # noqa: BLE001
            raise HHResumeVisibilityAutomationError(code="AUTH_SESSION_INVALID", message="Unable to load HH session state") from exc

        runtime = self.runtime_factory(storage_state)
        nav = HHNavigationHelper(page=runtime.page)
        runtime.page.goto("https://hh.ru/applicant/resumes")
        nav.require_authenticated_landing()
        nav.go_to_resumes()
        return runtime, nav

    def _open_visibility_controls(self, *, nav: HHNavigationHelper, managed_resume: HHManagedResume) -> None:
        summary = self._locate_resume(nav=nav, managed_resume=managed_resume)
        logger.info(
            "hh_resume_visibility_target_located managed_resume_id=%s strategy=%s",
            managed_resume.id,
            summary["match_strategy"],
        )
        if not nav.resumes_page.open_first_actions_menu():
            raise HHResumeVisibilityAutomationError(
                code="VISIBILITY_CONTROLS_NOT_FOUND",
                message="Unable to find resume actions menu",
            )
        if not nav.resumes_page.open_visibility_controls_from_menu():
            raise HHResumeVisibilityAutomationError(
                code="VISIBILITY_CONTROLS_NOT_FOUND",
                message="Unable to find visibility controls entry",
            )
        if not nav.resumes_page.visibility_dialog_detected():
            raise HHResumeVisibilityAutomationError(
                code="VISIBILITY_DIALOG_NOT_DETECTED",
                message="Visibility dialog/page was not detected",
            )

    def _locate_resume(self, *, nav: HHNavigationHelper, managed_resume: HHManagedResume) -> dict[str, str]:
        external_id = self._derive_external_id(managed_resume)
        if external_id and self._selector_exists(nav=nav, selector=f"a[href*='/resume/{external_id}']"):
            return {"match_strategy": "external_id", "external_id": external_id}

        if managed_resume.title and self._target_link_by_title(nav=nav, title=managed_resume.title):
            return {"match_strategy": "title", "title": managed_resume.title}

        if managed_resume.hh_resume_url and self._selector_exists(nav=nav, selector=f"a[href='{managed_resume.hh_resume_url}']"):
            return {"match_strategy": "resume_url", "resume_url": managed_resume.hh_resume_url}

        expanded = nav.resumes_page.expand_more_if_available()
        if expanded:
            if external_id and self._selector_exists(nav=nav, selector=f"a[href*='/resume/{external_id}']"):
                return {"match_strategy": "external_id_after_more", "external_id": external_id}
            if managed_resume.title and self._target_link_by_title(nav=nav, title=managed_resume.title):
                return {"match_strategy": "title_after_more", "title": managed_resume.title}

        raise HHResumeVisibilityAutomationError(
            code="RESUME_CARD_NOT_FOUND",
            message="Managed HH resume card was not found on resumes list",
        )

    def _target_link_by_title(self, *, nav: HHNavigationHelper, title: str) -> bool:
        title_locator = nav.page.get_by_role("link", name=title)
        if title_locator.count() > 0:
            return True
        return nav.page.get_by_text(title).count() > 0

    def _selector_exists(self, *, nav: HHNavigationHelper, selector: str) -> bool:
        return nav.page.locator(selector).count() > 0

    def _derive_external_id(self, managed_resume: HHManagedResume) -> str | None:
        if managed_resume.hh_resume_external_id:
            return managed_resume.hh_resume_external_id.strip()

        url = (managed_resume.hh_resume_url or "").strip()
        if not url:
            return None

        match = re.search(r"/resume/([A-Za-z0-9]+)", url)
        if match:
            return match.group(1)
        return None
