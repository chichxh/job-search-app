from __future__ import annotations

import logging
import time
from typing import Callable

from app.db.models import HHBrowserConnection
from app.schemas.hh_browser_integration import HHTargetedResumePayload
from app.services.hh_browser_connect_service import LocalSessionStorage
from app.services.hh_browser_page_objects import HHNavigationHelper, NormalizedAutomationError
from app.services.hh_browser_playwright import PlaywrightBrowserRuntime
from app.services.hh_resume_constructor_page_objects import HHResumeConstructorPageModel
from app.services.hh_targeted_resume_service import HHCreateResumeResult, HHResumeAutomationClient, HHResumeAutomationError

logger = logging.getLogger(__name__)


class PlaywrightTargetedResumeAutomationClient(HHResumeAutomationClient):
    def __init__(
        self,
        *,
        session_storage: LocalSessionStorage | None = None,
        runtime_factory: Callable[[dict], PlaywrightBrowserRuntime] | None = None,
    ) -> None:
        self.session_storage = session_storage or LocalSessionStorage()
        self.runtime_factory = runtime_factory or (lambda state: PlaywrightBrowserRuntime(storage_state=state))

    def create_targeted_resume(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        payload: HHTargetedResumePayload,
        dry_run: bool,
    ) -> HHCreateResumeResult:
        if dry_run:
            raise HHResumeAutomationError(code="invalid_mode", message="Dry-run mode cannot execute browser automation")
        if not connection.session_state_ref:
            raise HHResumeAutomationError(code="auth_session_missing", message="Active HH session state is missing")

        try:
            storage_state = self.session_storage.load(ref=connection.session_state_ref)
        except Exception as exc:  # noqa: BLE001
            raise HHResumeAutomationError(code="auth_session_invalid", message="Unable to load HH session state") from exc

        runtime = self.runtime_factory(storage_state)
        page = runtime.page
        nav = HHNavigationHelper(page=page)
        constructor = HHResumeConstructorPageModel(page=page)

        started = time.perf_counter()
        try:
            page.goto("https://hh.ru/applicant/resumes")
            nav.require_authenticated_landing()
            constructor.open_constructor()
            constructor.ensure_constructor_started()
            result = self._run_constructor(constructor=constructor, payload=payload)
            logger.info("hh_resume_constructor_completed user_id=%s elapsed_ms=%s", user_id, int((time.perf_counter() - started) * 1000))
            return result
        except NormalizedAutomationError as exc:
            raise HHResumeAutomationError(code=exc.code, message=exc.message) from exc
        except HHResumeAutomationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HHResumeAutomationError(code="constructor_layout_unknown", message="Unable to complete HH resume constructor flow") from exc
        finally:
            runtime.close()

    def _run_constructor(self, *, constructor: HHResumeConstructorPageModel, payload: HHTargetedResumePayload) -> HHCreateResumeResult:
        processed_steps: set[str] = set()
        for _ in range(14):
            step_started = time.perf_counter()
            step = constructor.detect_step()
            logger.info("hh_resume_constructor_step step=%s", step)

            if step == "success":
                external_id, resume_url, title = constructor.extract_success(payload.profession_title)
                if not external_id and resume_url:
                    external_id = resume_url.rstrip("/").split("/")[-1]
                if not external_id:
                    raise HHResumeAutomationError(code="success_not_verifiable", message="HH resume was submitted but ID is unavailable")
                return HHCreateResumeResult(external_id=external_id, resume_url=resume_url, title=title)

            if step == "phone_confirmation":
                raise HHResumeAutomationError(code="phone_confirmation_required", message="HH requires phone confirmation to continue")

            if step == "profession":
                constructor.fill_profession(payload.profession_title)
                constructor.continue_next()
                processed_steps.add("profession")
            elif step == "main_info":
                constructor.fill_main_info(title=payload.profession_title, summary=payload.summary)
                constructor.continue_next()
                processed_steps.add("main_info")
            elif step == "education":
                constructor.fill_education_minimum(payload.education)
                constructor.continue_next()
                processed_steps.add("education")
            elif step == "skills":
                constructor.fill_skills(payload.skills)
                constructor.continue_next()
                processed_steps.add("skills")
            elif step == "skill_levels":
                constructor.continue_next()
                processed_steps.add("skill_levels")
            elif step == "experience":
                constructor.fill_experience_minimum(payload.work_experience)
                constructor.continue_next()
                processed_steps.add("experience")
            elif step == "final":
                constructor.continue_next()
                processed_steps.add("final")
            else:
                if "profession" not in processed_steps:
                    raise HHResumeAutomationError(code="constructor_layout_unknown", message="Constructor step not recognized before profession")
                constructor.skip_or_continue(optional=False)

            logger.info("hh_resume_constructor_step_done step=%s duration_ms=%s", step, int((time.perf_counter() - step_started) * 1000))
            constructor.page.wait_for_timeout(350)

        raise HHResumeAutomationError(code="save_failed", message="HH resume constructor did not finish within supported steps")
