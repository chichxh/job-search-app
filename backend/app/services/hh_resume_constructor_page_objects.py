from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.hh_browser_error_taxonomy import AutomationErrorCode
from app.services.hh_browser_page_objects import (
    BasePageObject,
    BrowserPage,
    LocatorResolver,
    NormalizedAutomationError,
    SafeActionRunner,
    SelectorQuery,
)


@dataclass(frozen=True)
class ResumeConstructorSelectors:
    start_create_resume: tuple[SelectorQuery, ...]
    constructor_root: tuple[SelectorQuery, ...]
    profession_step: tuple[SelectorQuery, ...]
    profession_input: tuple[SelectorQuery, ...]
    profession_suggestion: tuple[SelectorQuery, ...]
    main_info_step: tuple[SelectorQuery, ...]
    title_input: tuple[SelectorQuery, ...]
    summary_input: tuple[SelectorQuery, ...]
    education_step: tuple[SelectorQuery, ...]
    education_institution: tuple[SelectorQuery, ...]
    skills_step: tuple[SelectorQuery, ...]
    skills_input: tuple[SelectorQuery, ...]
    skill_levels_step: tuple[SelectorQuery, ...]
    experience_step: tuple[SelectorQuery, ...]
    experience_company: tuple[SelectorQuery, ...]
    experience_position: tuple[SelectorQuery, ...]
    final_step: tuple[SelectorQuery, ...]
    success_markers: tuple[SelectorQuery, ...]
    next_controls: tuple[SelectorQuery, ...]
    skip_controls: tuple[SelectorQuery, ...]
    phone_confirmation_markers: tuple[SelectorQuery, ...]


DEFAULT_RESUME_CONSTRUCTOR_SELECTORS = ResumeConstructorSelectors(
    start_create_resume=(
        SelectorQuery("role", "Создать резюме", role="button"),
        SelectorQuery("role", "Создать резюме", role="link"),
        SelectorQuery("text", "Создать резюме"),
    ),
    constructor_root=(
        SelectorQuery("css", "[data-qa='resume-wizard']"),
        SelectorQuery("css", "form[action*='/resume']"),
        SelectorQuery("text", "Резюме"),
    ),
    profession_step=(
        SelectorQuery("text", "Професс"),
        SelectorQuery("css", "[data-qa='resume-profession-step']"),
    ),
    profession_input=(
        SelectorQuery("label", "Профессия"),
        SelectorQuery("label", "Должность"),
        SelectorQuery("css", "input[name*='profession']"),
        SelectorQuery("css", "input[name*='specialization']"),
    ),
    profession_suggestion=(
        SelectorQuery("css", "[data-qa='suggestion-item']"),
        SelectorQuery("css", "[role='option']"),
    ),
    main_info_step=(
        SelectorQuery("text", "Основная информация"),
        SelectorQuery("css", "[data-qa='resume-main-info-step']"),
    ),
    title_input=(
        SelectorQuery("label", "Желаемая должность"),
        SelectorQuery("label", "Должность"),
        SelectorQuery("css", "input[name*='title']"),
        SelectorQuery("css", "input[name*='position']"),
    ),
    summary_input=(
        SelectorQuery("label", "Обо мне"),
        SelectorQuery("css", "textarea[name*='about']"),
        SelectorQuery("css", "textarea[name*='summary']"),
    ),
    education_step=(
        SelectorQuery("text", "Образование"),
        SelectorQuery("css", "[data-qa='resume-education-step']"),
    ),
    education_institution=(
        SelectorQuery("label", "Учебное заведение"),
        SelectorQuery("css", "input[name*='institution']"),
    ),
    skills_step=(
        SelectorQuery("text", "Навык"),
        SelectorQuery("css", "[data-qa='resume-skills-step']"),
    ),
    skills_input=(
        SelectorQuery("label", "Навыки"),
        SelectorQuery("css", "input[name*='skill']"),
    ),
    skill_levels_step=(
        SelectorQuery("text", "Уровень навыков"),
        SelectorQuery("css", "[data-qa='resume-skill-levels-step']"),
    ),
    experience_step=(
        SelectorQuery("text", "Опыт работы"),
        SelectorQuery("css", "[data-qa='resume-experience-step']"),
    ),
    experience_company=(
        SelectorQuery("label", "Компания"),
        SelectorQuery("css", "input[name*='company']"),
    ),
    experience_position=(
        SelectorQuery("label", "Должность"),
        SelectorQuery("css", "input[name*='position']"),
    ),
    final_step=(
        SelectorQuery("text", "Опубликовать"),
        SelectorQuery("text", "Сохранить"),
    ),
    success_markers=(
        SelectorQuery("css", "a[href*='/resume/']"),
        SelectorQuery("text", "Резюме создано"),
        SelectorQuery("text", "Просмотр резюме"),
    ),
    next_controls=(
        SelectorQuery("role", "Продолжить", role="button"),
        SelectorQuery("role", "Дальше", role="button"),
        SelectorQuery("role", "Сохранить", role="button"),
        SelectorQuery("css", "button[type='submit']"),
    ),
    skip_controls=(
        SelectorQuery("role", "Пропустить", role="button"),
        SelectorQuery("text", "Пропустить"),
    ),
    phone_confirmation_markers=(
        SelectorQuery("text", "Подтвердите телефон"),
        SelectorQuery("text", "Подтверждение телефона"),
        SelectorQuery("text", "Код из СМС"),
    ),
)


class HHResumeConstructorPageModel(BasePageObject):
    def __init__(
        self,
        *,
        page: BrowserPage,
        selectors: ResumeConstructorSelectors = DEFAULT_RESUME_CONSTRUCTOR_SELECTORS,
        resolver: LocatorResolver | None = None,
        actions: SafeActionRunner | None = None,
    ) -> None:
        self.resume_selectors = selectors
        super().__init__(
            page=page,
            selectors=None,  # type: ignore[arg-type]
            resolver=resolver or LocatorResolver(page),
            actions=actions or SafeActionRunner(),
        )

    def open_constructor(self) -> None:
        create_btn = self.resolver.find_first(self.resume_selectors.start_create_resume)
        if create_btn is None:
            raise NormalizedAutomationError(
                "constructor_start_unavailable",
                "Create resume entry point is not available",
                debug_summary=self._summary(),
            )
        self.actions.run(action="open_constructor", callback=create_btn.click, debug_summary=lambda: self._summary())

    def ensure_constructor_started(self) -> None:
        if self.resolver.find_first(self.resume_selectors.constructor_root) is None and "/resume" not in self.page.url:
            raise NormalizedAutomationError(
                AutomationErrorCode.PAGE_NOT_RECOGNIZED,
                "Resume constructor root was not detected",
                debug_summary=self._summary(),
            )

    def detect_step(self) -> str:
        if self.resolver.find_first(self.resume_selectors.phone_confirmation_markers) is not None:
            return "phone_confirmation"
        if self.resolver.find_first(self.resume_selectors.success_markers) is not None and "/resume/" in self.page.url:
            return "success"
        if self.resolver.find_first(self.resume_selectors.profession_step) is not None:
            return "profession"
        if self.resolver.find_first(self.resume_selectors.main_info_step) is not None:
            return "main_info"
        if self.resolver.find_first(self.resume_selectors.education_step) is not None:
            return "education"
        if self.resolver.find_first(self.resume_selectors.skills_step) is not None:
            return "skills"
        if self.resolver.find_first(self.resume_selectors.skill_levels_step) is not None:
            return "skill_levels"
        if self.resolver.find_first(self.resume_selectors.experience_step) is not None:
            return "experience"
        if self.resolver.find_first(self.resume_selectors.final_step) is not None:
            return "final"
        return "unknown"

    def fill_profession(self, profession_title: str) -> None:
        input_locator = self.resolver.find_first(self.resume_selectors.profession_input)
        if input_locator is None:
            raise NormalizedAutomationError("profession_not_selectable", "Unable to locate profession field", debug_summary=self._summary())
        self.actions.run(action="fill_profession", callback=lambda: input_locator.fill(profession_title), debug_summary=lambda: self._summary())
        suggestion = self.page.get_by_text(profession_title)
        if suggestion.count() > 0:
            self.actions.run(action="profession_suggestion_exact", callback=suggestion.first.click, debug_summary=lambda: self._summary())
            return
        fallback = self.resolver.find_first(self.resume_selectors.profession_suggestion)
        if fallback is not None:
            self.actions.run(action="profession_suggestion_fallback", callback=fallback.click, debug_summary=lambda: self._summary())

    def fill_main_info(self, *, title: str, summary: str) -> None:
        title_input = self.resolver.find_first(self.resume_selectors.title_input)
        if title_input is not None:
            self.actions.run(action="fill_title", callback=lambda: title_input.fill(title), debug_summary=lambda: self._summary())
        summary_input = self.resolver.find_first(self.resume_selectors.summary_input)
        if summary_input is not None and summary.strip():
            self.actions.run(action="fill_summary", callback=lambda: summary_input.fill(summary[:3000]), debug_summary=lambda: self._summary())

    def fill_education_minimum(self, education: list[dict[str, Any]]) -> None:
        if not education:
            self.skip_or_continue(optional=True)
            return
        institution = self.resolver.find_first(self.resume_selectors.education_institution)
        if institution is None:
            self.skip_or_continue(optional=True)
            return
        value = (education[0].get("institution") or "").strip()
        if value:
            self.actions.run(action="fill_education", callback=lambda: institution.fill(value), debug_summary=lambda: self._summary())

    def fill_skills(self, skills: list[str]) -> None:
        if not skills:
            self.skip_or_continue(optional=True)
            return
        input_locator = self.resolver.find_first(self.resume_selectors.skills_input)
        if input_locator is None:
            self.skip_or_continue(optional=True)
            return
        for skill in skills[:8]:
            text = skill.strip()
            if not text:
                continue
            self.actions.run(action="fill_skill", callback=lambda value=text: input_locator.fill(value), debug_summary=lambda: self._summary())

    def fill_experience_minimum(self, experiences: list[dict[str, Any]]) -> None:
        if not experiences:
            self.skip_or_continue(optional=True)
            return
        company = self.resolver.find_first(self.resume_selectors.experience_company)
        position = self.resolver.find_first(self.resume_selectors.experience_position)
        first = experiences[0]
        if company is not None and first.get("company_name"):
            self.actions.run(action="fill_experience_company", callback=lambda: company.fill(str(first["company_name"])[:255]), debug_summary=lambda: self._summary())
        if position is not None and first.get("position_title"):
            self.actions.run(action="fill_experience_position", callback=lambda: position.fill(str(first["position_title"])[:255]), debug_summary=lambda: self._summary())

    def continue_next(self) -> None:
        next_btn = self.resolver.find_first(self.resume_selectors.next_controls)
        if next_btn is None:
            raise NormalizedAutomationError("save_failed", "Unable to continue constructor flow", debug_summary=self._summary())
        self.actions.run(action="continue_next", callback=next_btn.click, debug_summary=lambda: self._summary())

    def skip_or_continue(self, *, optional: bool) -> None:
        skip_btn = self.resolver.find_first(self.resume_selectors.skip_controls)
        if skip_btn is not None:
            self.actions.run(action="skip_step", callback=skip_btn.click, debug_summary=lambda: self._summary())
            return
        if optional:
            self.continue_next()
            return
        raise NormalizedAutomationError("unsupported_required_step", "Unsupported required constructor step", debug_summary=self._summary())

    def extract_success(self, fallback_title: str) -> tuple[str | None, str | None, str]:
        url = self.page.url if "/resume/" in self.page.url else None
        external_id = None
        if url:
            parts = [item for item in url.rstrip("/").split("/") if item]
            external_id = parts[-1] if parts else None
        return external_id, url, fallback_title
