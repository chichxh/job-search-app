from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Callable

from app.db.models import HHApplyRun, HHBrowserConnection, HHManagedResume, Vacancy
from app.services.hh_apply_service import HHApplyAutomationError, HHApplyAutomationResult
from app.services.hh_browser_connect_service import LocalSessionStorage
from app.services.hh_browser_page_objects import HHNavigationHelper, NormalizedAutomationError
from app.services.hh_browser_playwright import PlaywrightBrowserRuntime

logger = logging.getLogger(__name__)


class PlaywrightHHApplyAutomationClient:
    allow_optional_empty_cover_letter = True

    def __init__(
        self,
        *,
        session_storage: LocalSessionStorage | None = None,
        runtime_factory: Callable[[dict], PlaywrightBrowserRuntime] | None = None,
    ) -> None:
        self.session_storage = session_storage or LocalSessionStorage()
        self.runtime_factory = runtime_factory or (lambda state: PlaywrightBrowserRuntime(storage_state=state))

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

        runtime, nav = self._open_runtime(connection=connection)
        started_perf = time.perf_counter()
        try:
            vacancy_url = self._resolve_vacancy_url(vacancy)
            self._log_step("open_vacancy", apply_run_id=apply_run.id, user_id=user_id)
            nav.open_vacancy(vacancy_url)
            if nav.vacancy_page.detect_unavailable():
                raise HHApplyAutomationError(
                    code="VACANCY_PAGE_UNAVAILABLE",
                    message="HH vacancy page is unavailable or archived",
                    response_ref=self._response_ref(vacancy_url=runtime.page.url, hh_response_type="vacancy_unavailable"),
                )
            if nav.apply_page.detect_already_applied():
                return HHApplyAutomationResult(
                    result_type="already_applied",
                    result_message="Response already exists for this vacancy",
                    response_ref=self._response_ref(vacancy_url=runtime.page.url, hh_response_type="already_applied"),
                )
            if nav.apply_page.detect_cannot_apply():
                raise HHApplyAutomationError(
                    code="RESPONSE_UNAVAILABLE",
                    message="Vacancy does not accept responses right now",
                    response_ref=self._response_ref(vacancy_url=runtime.page.url, hh_response_type="response_unavailable"),
                )
            if not nav.vacancy_page.detect_apply_entry():
                raise HHApplyAutomationError(
                    code="APPLY_ENTRY_NOT_FOUND",
                    message="Vacancy apply action is not available",
                    response_ref=self._response_ref(vacancy_url=runtime.page.url, hh_response_type="apply_entry_missing"),
                )

            self._log_step("open_apply_surface", apply_run_id=apply_run.id, user_id=user_id)
            nav.open_apply_surface()
            outcome = self._detect_pre_submit_terminal_state(nav=nav, vacancy_url=runtime.page.url)
            if outcome is not None:
                return outcome

            if self._auto_hide_enabled(managed_resume):
                self._log_step("privacy_precheck", apply_run_id=apply_run.id, user_id=user_id)
                self._ensure_resume_hidden_from_all(nav=nav, managed_resume=managed_resume)
                self._log_step("privacy_precheck_confirmed", apply_run_id=apply_run.id, user_id=user_id)
                self._log_step("open_vacancy", apply_run_id=apply_run.id, user_id=user_id)
                nav.open_vacancy(vacancy_url)
                self._log_step("open_apply_surface", apply_run_id=apply_run.id, user_id=user_id)
                nav.open_apply_surface()
                outcome = self._detect_pre_submit_terminal_state(nav=nav, vacancy_url=runtime.page.url)
                if outcome is not None:
                    return outcome
            else:
                self._log_step("privacy_precheck_skipped", apply_run_id=apply_run.id, user_id=user_id)

            self._select_resume(nav=nav, managed_resume=managed_resume)
            self._fill_cover_letter(nav=nav, cover_letter_text=cover_letter_text)

            self._log_step("submit_apply", apply_run_id=apply_run.id, user_id=user_id)
            if not nav.apply_page.submit():
                raise HHApplyAutomationError(code="APPLY_SUBMIT_NOT_FOUND", message="Final apply submit action not found")
            runtime.page.wait_for_timeout(500)

            outcome = self._detect_post_submit_state(nav=nav, vacancy_url=runtime.page.url)
            if outcome is not None:
                return outcome

            raise HHApplyAutomationError(code="APPLY_SUBMIT_FAILED", message="Apply submit could not be verified")
        except NormalizedAutomationError as exc:
            raise HHApplyAutomationError(code=exc.code.upper(), message=exc.message, retryable=True) from exc
        finally:
            logger.info(
                "hh_apply_automation_finished user_id=%s apply_run_id=%s duration_ms=%s",
                user_id,
                apply_run.id,
                int((time.perf_counter() - started_perf) * 1000),
            )
            runtime.close()

    def _open_runtime(self, *, connection: HHBrowserConnection) -> tuple[PlaywrightBrowserRuntime, HHNavigationHelper]:
        if not connection.session_state_ref:
            raise HHApplyAutomationError(code="SESSION_EXPIRED", message="Active HH session state is missing", retryable=True)
        try:
            storage_state = self.session_storage.load(ref=connection.session_state_ref)
        except Exception as exc:  # noqa: BLE001
            raise HHApplyAutomationError(code="SESSION_EXPIRED", message="Unable to load HH session state", retryable=True) from exc

        runtime = self.runtime_factory(storage_state)
        nav = HHNavigationHelper(page=runtime.page)
        runtime.page.goto("https://hh.ru/applicant/resumes")
        report = nav.ensure_authenticated_landing()
        if not report["page_detected"]:
            runtime.close()
            raise HHApplyAutomationError(code="SESSION_EXPIRED", message="HH authentication is not active", retryable=True)
        return runtime, nav

    def _resolve_vacancy_url(self, vacancy: Vacancy) -> str:
        if vacancy.url:
            return vacancy.url
        ext = (vacancy.external_ref or "").strip()
        if ext.isdigit():
            return f"https://hh.ru/vacancy/{ext}"
        if ext:
            match = re.search(r"(\d+)", ext)
            if match:
                return f"https://hh.ru/vacancy/{match.group(1)}"
        raise HHApplyAutomationError(code="VACANCY_URL_UNAVAILABLE", message="Vacancy URL is unavailable for HH apply")

    def _select_resume(self, *, nav: HHNavigationHelper, managed_resume: HHManagedResume) -> None:
        if not nav.apply_page.has_resume_selection():
            return

        external_id = self._derive_external_id(managed_resume)
        if external_id and nav.apply_page.select_resume_by_external_id(external_id=external_id):
            return
        if managed_resume.hh_resume_url and nav.apply_page.select_resume_by_url(resume_url=managed_resume.hh_resume_url):
            return
        if managed_resume.title and nav.apply_page.select_resume_by_title(title=managed_resume.title):
            return
        if nav.apply_page.select_single_resume_fallback():
            logger.warning(
                "hh_apply_resume_selection_fallback strategy=single_resume_card managed_resume_id=%s",
                managed_resume.id,
            )
            return

        raise HHApplyAutomationError(
            code="TARGET_RESUME_NOT_SELECTABLE",
            message="Target managed resume cannot be identified on apply surface",
            response_ref={"hh_response_type": "resume_selection_failed"},
        )

    def _fill_cover_letter(self, *, nav: HHNavigationHelper, cover_letter_text: str | None) -> None:
        has_field = nav.apply_page.has_cover_letter_input()
        if not has_field:
            return

        if cover_letter_text:
            nav.apply_page.fill_cover_letter(text=cover_letter_text)
            logger.info("hh_apply_cover_letter_filled length=%s", len(cover_letter_text))
            return

        if nav.apply_page.is_cover_letter_required():
            raise HHApplyAutomationError(
                code="COVER_LETTER_REQUIRED",
                message="Cover letter is required for this vacancy",
                response_ref={"hh_response_type": "cover_letter_required"},
            )
        if not self.allow_optional_empty_cover_letter:
            raise HHApplyAutomationError(
                code="COVER_LETTER_POLICY_BLOCKED",
                message="Cover letter policy blocks empty optional cover letter",
                response_ref={"hh_response_type": "cover_letter_policy_blocked"},
            )

    def _detect_pre_submit_terminal_state(self, *, nav: HHNavigationHelper, vacancy_url: str) -> HHApplyAutomationResult | None:
        if nav.apply_page.detect_auth_lost():
            raise HHApplyAutomationError(code="SESSION_EXPIRED", message="HH session expired during apply flow", retryable=True)
        if nav.apply_page.detect_already_applied():
            return HHApplyAutomationResult(
                result_type="already_applied",
                result_message="Response already exists for this vacancy",
                response_ref=self._response_ref(vacancy_url=vacancy_url, hh_response_type="already_applied"),
            )
        if nav.apply_page.detect_cannot_apply():
            raise HHApplyAutomationError(
                code="RESPONSE_UNAVAILABLE",
                message="Vacancy does not accept responses",
                response_ref=self._response_ref(vacancy_url=vacancy_url, hh_response_type="response_unavailable"),
            )
        return None

    def _detect_post_submit_state(self, *, nav: HHNavigationHelper, vacancy_url: str) -> HHApplyAutomationResult | None:
        if nav.apply_page.detect_success() or nav.apply_page.detect_already_applied():
            summary = "Отклик отправлен" if nav.apply_page.detect_success() else "Отклик уже существует"
            return HHApplyAutomationResult(
                result_type="submitted",
                result_message="Apply submitted via HH browser automation",
                response_ref=self._response_ref(
                    vacancy_url=vacancy_url,
                    hh_response_type="submitted",
                    confirmation_summary=summary,
                ),
            )
        if nav.apply_page.detect_auth_lost():
            raise HHApplyAutomationError(code="SESSION_EXPIRED", message="HH session expired after submit", retryable=True)
        if nav.apply_page.detect_cannot_apply():
            raise HHApplyAutomationError(code="RESPONSE_UNAVAILABLE", message="Response became unavailable during submit")
        return None


    def _ensure_resume_hidden_from_all(self, *, nav: HHNavigationHelper, managed_resume: HHManagedResume) -> None:
        nav.go_to_resumes()
        if not self._locate_resume(nav=nav, managed_resume=managed_resume):
            raise HHApplyAutomationError(
                code="VISIBILITY_PRECONDITION_FAILED",
                message="Unable to locate target resume card in HH settings",
                response_ref={"hh_response_type": "visibility_precondition_failed", "reason": "resume_card_not_found"},
            )
        if not nav.resumes_page.open_first_actions_menu() or not nav.resumes_page.open_visibility_controls_from_menu():
            raise HHApplyAutomationError(
                code="VISIBILITY_PRECONDITION_FAILED",
                message="Unable to open visibility controls for target resume",
                response_ref={"hh_response_type": "visibility_precondition_failed", "reason": "visibility_controls_not_found"},
            )
        if not nav.resumes_page.visibility_dialog_detected():
            raise HHApplyAutomationError(
                code="VISIBILITY_PRECONDITION_FAILED",
                message="Visibility controls page was not detected",
                response_ref={"hh_response_type": "visibility_precondition_failed", "reason": "visibility_dialog_not_detected"},
            )
        current = nav.resumes_page.detect_visibility_mode()
        if current == "hidden_from_all":
            return
        if current == "unknown":
            raise HHApplyAutomationError(
                code="VISIBILITY_PRECONDITION_FAILED",
                message="Unable to determine current resume visibility mode",
                response_ref={"hh_response_type": "visibility_precondition_failed", "reason": "unknown_visibility_layout"},
            )
        if not nav.resumes_page.select_hide_from_all():
            raise HHApplyAutomationError(
                code="VISIBILITY_PRECONDITION_FAILED",
                message="Hide-from-all option is unavailable in HH layout",
                response_ref={"hh_response_type": "visibility_precondition_failed", "reason": "hidden_option_unavailable"},
            )
        if not nav.resumes_page.save_visibility():
            raise HHApplyAutomationError(
                code="VISIBILITY_PRECONDITION_FAILED",
                message="Visibility save action was not found",
                response_ref={"hh_response_type": "visibility_precondition_failed", "reason": "save_failed"},
            )
        updated = nav.resumes_page.detect_visibility_mode()
        if not (nav.resumes_page.visibility_success_detected() or updated == "hidden_from_all"):
            raise HHApplyAutomationError(
                code="VISIBILITY_PRECONDITION_FAILED",
                message="Unable to verify hidden visibility mode after save",
                response_ref={"hh_response_type": "visibility_precondition_failed", "reason": "post_save_verification_failed"},
            )

    def _locate_resume(self, *, nav: HHNavigationHelper, managed_resume: HHManagedResume) -> bool:
        external_id = self._derive_external_id(managed_resume)
        if external_id and self._selector_exists(nav=nav, selector=f"a[href*='/resume/{external_id}']"):
            return True
        if managed_resume.title and self._target_link_by_title(nav=nav, title=managed_resume.title):
            return True
        if managed_resume.hh_resume_url and self._selector_exists(nav=nav, selector=f"a[href='{managed_resume.hh_resume_url}']"):
            return True
        if nav.resumes_page.expand_more_if_available():
            if external_id and self._selector_exists(nav=nav, selector=f"a[href*='/resume/{external_id}']"):
                return True
            if managed_resume.title and self._target_link_by_title(nav=nav, title=managed_resume.title):
                return True
            if managed_resume.hh_resume_url and self._selector_exists(nav=nav, selector=f"a[href='{managed_resume.hh_resume_url}']"):
                return True
        return False

    def _target_link_by_title(self, *, nav: HHNavigationHelper, title: str) -> bool:
        title_locator = nav.page.get_by_role("link", name=title)
        if title_locator.count() > 0:
            return True
        return nav.page.get_by_text(title).count() > 0

    def _selector_exists(self, *, nav: HHNavigationHelper, selector: str) -> bool:
        return nav.page.locator(selector).count() > 0

    def _auto_hide_enabled(self, managed_resume: HHManagedResume) -> bool:
        return getattr(managed_resume, "auto_hide_from_all_enabled", True) is not False

    def _response_ref(self, *, vacancy_url: str, hh_response_type: str, confirmation_summary: str | None = None) -> dict[str, str]:
        payload = {
            "hh_response_type": hh_response_type,
            "vacancy_url": vacancy_url,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }
        if confirmation_summary:
            payload["confirmation_summary"] = confirmation_summary[:80]
        return payload

    def _derive_external_id(self, managed_resume: HHManagedResume) -> str | None:
        if managed_resume.hh_resume_external_id:
            return managed_resume.hh_resume_external_id.strip()
        url = (managed_resume.hh_resume_url or "").strip()
        match = re.search(r"/resume/([A-Za-z0-9]+)", url)
        if match:
            return match.group(1)
        return None

    def _log_step(self, step: str, *, apply_run_id: int, user_id: int) -> None:
        logger.info("hh_apply_step step=%s user_id=%s apply_run_id=%s", step, user_id, apply_run_id)
