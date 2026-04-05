from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from app.services.hh_browser_error_taxonomy import AutomationErrorCode


class NormalizedAutomationError(Exception):
    def __init__(self, code: str, message: str, *, debug_summary: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.debug_summary = debug_summary or {}


StepCode = Literal["identifier", "password", "code", "authenticated", "unknown"]
IdentifierType = Literal["phone", "email"]


class BrowserLocator(Protocol):
    @property
    def first(self) -> "BrowserLocator": ...

    def count(self) -> int: ...

    def fill(self, value: str) -> None: ...

    def click(self) -> None: ...


class BrowserPage(Protocol):
    url: str

    def title(self) -> str: ...
    def goto(self, url: str) -> None: ...

    def get_by_role(self, role: str, *, name: str) -> BrowserLocator: ...

    def get_by_label(self, text: str) -> BrowserLocator: ...

    def get_by_text(self, text: str) -> BrowserLocator: ...

    def locator(self, selector: str) -> BrowserLocator: ...

    def wait_for_timeout(self, timeout_ms: int) -> None: ...

    def screenshot(self, *, path: str, full_page: bool = True) -> None: ...


@dataclass(frozen=True)
class SelectorQuery:
    strategy: Literal["role", "label", "text", "css"]
    value: str
    role: str | None = None

    def as_locator_hint(self) -> str:
        if self.strategy == "role":
            return f"role:{self.role}:{self.value}"
        return f"{self.strategy}:{self.value}"


@dataclass(frozen=True)
class SelectorMatchDiagnostics:
    matched: bool
    matched_query: str | None
    used_fallback: bool
    strategy: str | None


@dataclass(frozen=True)
class LoginSelectorGroup:
    identifier_phone: tuple[SelectorQuery, ...]
    identifier_email: tuple[SelectorQuery, ...]
    password_input: tuple[SelectorQuery, ...]
    code_input: tuple[SelectorQuery, ...]
    continue_button: tuple[SelectorQuery, ...]
    submit_button: tuple[SelectorQuery, ...]
    password_entry_button: tuple[SelectorQuery, ...]
    authenticated_markers: tuple[SelectorQuery, ...]


@dataclass(frozen=True)
class ApplicantHomeSelectorGroup:
    home_markers: tuple[SelectorQuery, ...]
    resumes_nav: tuple[SelectorQuery, ...]


@dataclass(frozen=True)
class ResumesListSelectorGroup:
    list_markers: tuple[SelectorQuery, ...]
    resume_cards: tuple[SelectorQuery, ...]
    create_resume: tuple[SelectorQuery, ...]
    edit_resume: tuple[SelectorQuery, ...]
    show_more: tuple[SelectorQuery, ...]
    resume_actions_menu: tuple[SelectorQuery, ...]
    visibility_menu_entry: tuple[SelectorQuery, ...]
    visibility_dialog_markers: tuple[SelectorQuery, ...]
    visibility_public_markers: tuple[SelectorQuery, ...]
    visibility_hidden_markers: tuple[SelectorQuery, ...]
    visibility_hide_from_all: tuple[SelectorQuery, ...]
    visibility_save: tuple[SelectorQuery, ...]
    visibility_success: tuple[SelectorQuery, ...]


@dataclass(frozen=True)
class ResumeEditorSelectorGroup:
    editor_markers: tuple[SelectorQuery, ...]
    section_markers: tuple[SelectorQuery, ...]
    visibility_controls: tuple[SelectorQuery, ...]
    save_controls: tuple[SelectorQuery, ...]


@dataclass(frozen=True)
class VacancySelectorGroup:
    vacancy_markers: tuple[SelectorQuery, ...]
    apply_entry: tuple[SelectorQuery, ...]
    company_markers: tuple[SelectorQuery, ...]


@dataclass(frozen=True)
class ApplySurfaceSelectorGroup:
    surface_markers: tuple[SelectorQuery, ...]
    resume_selector: tuple[SelectorQuery, ...]
    cover_letter_input: tuple[SelectorQuery, ...]
    submit_controls: tuple[SelectorQuery, ...]


@dataclass(frozen=True)
class SelectorRegistry:
    login: LoginSelectorGroup
    applicant_home: ApplicantHomeSelectorGroup
    resumes_list: ResumesListSelectorGroup
    resume_editor: ResumeEditorSelectorGroup
    vacancy: VacancySelectorGroup
    apply_surface: ApplySurfaceSelectorGroup


DEFAULT_SELECTORS = SelectorRegistry(
    login=LoginSelectorGroup(
        # PRIMARY: human-visible labels are most stable for i18n login forms.
        # FALLBACK: type/name CSS handles HH experiments with anonymous inputs.
        identifier_phone=(
        SelectorQuery("label", "Телефон"),
        SelectorQuery("label", "Телефон или почта"),
        SelectorQuery("css", "input[type='tel']"),
        SelectorQuery("css", "input[name*='login']"),
        ),
        identifier_email=(
        SelectorQuery("label", "Почта"),
        SelectorQuery("label", "Телефон или почта"),
        SelectorQuery("css", "input[type='email']"),
        SelectorQuery("css", "input[name*='username']"),
        ),
        password_input=(
        # PRIMARY: explicit "Пароль" label. FALLBACK: semantic password inputs.
        SelectorQuery("label", "Пароль"),
        SelectorQuery("css", "input[type='password']"),
        SelectorQuery("css", "input[name*='password']"),
        ),
        code_input=(
        # OTP UI variants observed across SMS/confirmation flavors.
        SelectorQuery("label", "Код"),
        SelectorQuery("label", "Код из SMS"),
        SelectorQuery("label", "Код подтверждения"),
        SelectorQuery("css", "input[inputmode='numeric']"),
        SelectorQuery("css", "input[name*='otp']"),
        SelectorQuery("css", "input[name*='code']"),
        ),
        continue_button=(
        # Keep continue separate from submit to detect identifier step robustly.
        SelectorQuery("role", "Дальше", role="button"),
        SelectorQuery("role", "Продолжить", role="button"),
        ),
        submit_button=(
        SelectorQuery("role", "Войти", role="button"),
        SelectorQuery("role", "Подтвердить", role="button"),
        SelectorQuery("role", "Продолжить", role="button"),
        SelectorQuery("css", "button[type='submit']"),
        ),
        password_entry_button=(
        SelectorQuery("role", "Войти с паролем", role="button"),
        SelectorQuery("text", "Войти с паролем"),
        ),
        authenticated_markers=(
        SelectorQuery("css", "[data-qa='mainmenu_applicantProfile']"),
        SelectorQuery("css", "a[href*='/applicant']"),
        ),
    ),
    applicant_home=ApplicantHomeSelectorGroup(
        home_markers=(
            SelectorQuery("css", "[data-qa='applicant-dashboard']"),
            SelectorQuery("css", "[data-qa='mainmenu_applicantProfile']"),
            SelectorQuery("css", "a[href*='/applicant/resumes']"),
        ),
        resumes_nav=(
            SelectorQuery("role", "Мои резюме", role="link"),
            SelectorQuery("text", "Резюме"),
            SelectorQuery("css", "a[href*='/applicant/resumes']"),
        ),
    ),
    resumes_list=ResumesListSelectorGroup(
        list_markers=(
            SelectorQuery("css", "[data-qa='resume-list']"),
            SelectorQuery("css", "[data-qa='resumes-title']"),
            SelectorQuery("css", "a[href*='/resume/']"),
        ),
        resume_cards=(
            SelectorQuery("css", "[data-qa='resume-card']"),
            SelectorQuery("css", "[data-qa='resume-title']"),
            SelectorQuery("css", "a[href*='/resume/']"),
        ),
        create_resume=(
            SelectorQuery("role", "Создать резюме", role="button"),
            SelectorQuery("role", "Создать резюме", role="link"),
            SelectorQuery("text", "Создать резюме"),
            SelectorQuery("css", "a[href*='/resume/new']"),
        ),
        edit_resume=(
            SelectorQuery("role", "Редактировать", role="link"),
            SelectorQuery("text", "Редактировать"),
            SelectorQuery("css", "a[href*='/resume/'][href*='/edit']"),
        ),
        show_more=(
            SelectorQuery("role", "Подробнее", role="button"),
            SelectorQuery("text", "Подробнее"),
            SelectorQuery("css", "[data-qa*='resumes-list-more']"),
        ),
        resume_actions_menu=(
            SelectorQuery("css", "[data-qa*='resume-actions']"),
            SelectorQuery("css", "[data-qa*='resume-menu']"),
            SelectorQuery("role", "Ещё", role="button"),
        ),
        visibility_menu_entry=(
            SelectorQuery("role", "Изменить видимость", role="menuitem"),
            SelectorQuery("role", "Изменить видимость", role="button"),
            SelectorQuery("text", "Изменить видимость"),
        ),
        visibility_dialog_markers=(
            SelectorQuery("text", "Видимость резюме"),
            SelectorQuery("text", "Кто видит резюме"),
            SelectorQuery("css", "[data-qa*='resume-visibility']"),
        ),
        visibility_public_markers=(
            SelectorQuery("text", "Видно всем работодателям"),
            SelectorQuery("text", "Доступно всем работодателям"),
            SelectorQuery("text", "Видно всем"),
        ),
        visibility_hidden_markers=(
            SelectorQuery("text", "Скрыто от всех"),
            SelectorQuery("text", "Только вам"),
        ),
        visibility_hide_from_all=(
            SelectorQuery("role", "Просто скрыть от всех", role="radio"),
            SelectorQuery("role", "Скрыто от всех", role="radio"),
            SelectorQuery("role", "Только вам", role="radio"),
            SelectorQuery("text", "Просто скрыть от всех"),
            SelectorQuery("text", "Скрыто от всех"),
        ),
        visibility_save=(
            SelectorQuery("role", "Сохранить", role="button"),
            SelectorQuery("role", "Применить", role="button"),
            SelectorQuery("text", "Сохранить"),
            SelectorQuery("css", "button[type='submit']"),
        ),
        visibility_success=(
            SelectorQuery("text", "Изменения сохранены"),
            SelectorQuery("text", "Видимость обновлена"),
            SelectorQuery("text", "Скрыто от всех"),
        ),
    ),
    resume_editor=ResumeEditorSelectorGroup(
        editor_markers=(
            SelectorQuery("css", "[data-qa='resume-form']"),
            SelectorQuery("css", "[data-qa='resume-editor']"),
            SelectorQuery("css", "form[action*='/resume']"),
        ),
        section_markers=(
            SelectorQuery("css", "[data-qa='resume-block-title']"),
            SelectorQuery("css", "[data-qa='resume-block-experience']"),
            SelectorQuery("label", "Желаемая должность"),
        ),
        visibility_controls=(
            SelectorQuery("text", "Видимость резюме"),
            SelectorQuery("text", "Доступность резюме"),
            SelectorQuery("css", "[data-qa*='resume-visibility']"),
        ),
        save_controls=(
            SelectorQuery("role", "Сохранить", role="button"),
            SelectorQuery("role", "Продолжить", role="button"),
            SelectorQuery("css", "button[type='submit']"),
        ),
    ),
    vacancy=VacancySelectorGroup(
        vacancy_markers=(
            # PRIMARY vacancy identity markers; keep apply selector separate for diagnostics.
            SelectorQuery("css", "[data-qa='vacancy-title']"),
            SelectorQuery("css", "[data-qa='vacancy-response-link-top']"),
            SelectorQuery("css", "[data-qa='vacancy-company-name']"),
        ),
        apply_entry=(
            SelectorQuery("role", "Откликнуться", role="button"),
            SelectorQuery("role", "Откликнуться", role="link"),
            SelectorQuery("css", "[data-qa='vacancy-response-link-top']"),
            SelectorQuery("css", "[data-qa='vacancy-response-link-bottom']"),
        ),
        company_markers=(
            SelectorQuery("css", "[data-qa='vacancy-company-name']"),
            SelectorQuery("css", "[data-qa='vacancy-company-logo']"),
        ),
    ),
    apply_surface=ApplySurfaceSelectorGroup(
        surface_markers=(
            # Modal/popup form markers for in-page apply experience.
            SelectorQuery("css", "[data-qa='vacancy-response-popup']"),
            SelectorQuery("css", "[data-qa='vacancy-response-form']"),
            SelectorQuery("text", "Отклик на вакансию"),
        ),
        resume_selector=(
            SelectorQuery("css", "[data-qa='resume-select']"),
            SelectorQuery("label", "Резюме"),
            SelectorQuery("text", "Выберите резюме"),
        ),
        cover_letter_input=(
            SelectorQuery("label", "Сопроводительное письмо"),
            SelectorQuery("css", "textarea[name*='cover']"),
            SelectorQuery("css", "[data-qa='vacancy-response-popup-form-letter-input']"),
        ),
        submit_controls=(
            SelectorQuery("role", "Отправить", role="button"),
            SelectorQuery("role", "Откликнуться", role="button"),
            SelectorQuery("css", "button[type='submit']"),
        ),
    ),
)


class LocatorResolver:
    def __init__(self, page: BrowserPage) -> None:
        self.page = page

    def find_first(self, queries: tuple[SelectorQuery, ...]) -> BrowserLocator | None:
        result = self.find_first_with_diagnostics(queries)
        return result[0]

    def find_first_with_diagnostics(self, queries: tuple[SelectorQuery, ...]) -> tuple[BrowserLocator | None, SelectorMatchDiagnostics]:
        for query in queries:
            locator = self._resolve(query)
            if locator is None:
                continue
            if locator.count() > 0:
                return (
                    locator.first,
                    SelectorMatchDiagnostics(
                        matched=True,
                        matched_query=query.as_locator_hint(),
                        used_fallback=query != queries[0],
                        strategy=query.strategy,
                    ),
                )
        return (None, SelectorMatchDiagnostics(matched=False, matched_query=None, used_fallback=False, strategy=None))

    def _resolve(self, query: SelectorQuery) -> BrowserLocator | None:
        if query.strategy == "label":
            return self.page.get_by_label(query.value)
        if query.strategy == "role":
            if query.role is None:
                return None
            return self.page.get_by_role(query.role, name=query.value)
        if query.strategy == "text":
            return self.page.get_by_text(query.value)
        if query.strategy == "css":
            return self.page.locator(query.value)
        return None

    def count_first(self, queries: tuple[SelectorQuery, ...]) -> int:
        for query in queries:
            locator = self._resolve(query)
            if locator is not None and locator.count() > 0:
                return locator.count()
        return 0


class SafeActionRunner:
    def __init__(self, *, default_timeout_ms: int = 12000, retries: int = 1) -> None:
        self.default_timeout_ms = default_timeout_ms
        self.retries = retries

    def run(self, *, action: str, callback: Callable[[], Any], debug_summary: Callable[[], dict[str, Any]]) -> Any:
        attempts = max(1, self.retries)
        for attempt in range(1, attempts + 1):
            try:
                return callback()
            except NormalizedAutomationError:
                raise
            except Exception as exc:  # noqa: BLE001
                if attempt >= attempts:
                    raise NormalizedAutomationError(
                        AutomationErrorCode.CONTROL_NOT_INTERACTABLE,
                        f"Action failed: {action}",
                        debug_summary=debug_summary(),
                    ) from exc

        raise NormalizedAutomationError(
            AutomationErrorCode.CONTROL_NOT_INTERACTABLE,
            f"Action failed: {action}",
            debug_summary=debug_summary(),
        )


@dataclass(frozen=True)
class StepDetectionResult:
    step_code: StepCode
    summary: dict[str, Any]


class BasePageObject:
    def __init__(self, *, page: BrowserPage, selectors: SelectorRegistry, resolver: LocatorResolver, actions: SafeActionRunner) -> None:
        self.page = page
        self.selectors = selectors
        self.resolver = resolver
        self.actions = actions

    def _summary(self, **extra: Any) -> dict[str, Any]:
        summary = {
            "url": self.page.url,
            "title": self.page.title(),
        }
        summary.update(extra)
        return summary

    def _selector_report(
        self,
        *,
        page_name: str,
        required_controls: dict[str, tuple[SelectorQuery, ...]],
        optional_controls: dict[str, tuple[SelectorQuery, ...]] | None = None,
    ) -> dict[str, Any]:
        optional_controls = optional_controls or {}
        primary_matches: dict[str, str | None] = {}
        fallback_controls: list[str] = []
        missing_required: list[str] = []
        selector_health: dict[str, dict[str, Any]] = {}

        for control, queries in {**required_controls, **optional_controls}.items():
            _, diag = self.resolver.find_first_with_diagnostics(queries)
            selector_health[control] = {
                "matched": diag.matched,
                "matched_query": diag.matched_query,
                "used_fallback": diag.used_fallback,
                "strategy": diag.strategy,
            }
            if diag.matched:
                primary_matches[control] = diag.matched_query
                if diag.used_fallback:
                    fallback_controls.append(control)
            elif control in required_controls:
                missing_required.append(control)

        return self._summary(
            page=page_name,
            page_detected=len(missing_required) == 0,
            primary_selectors_matched=primary_matches,
            fallback_selectors_used=fallback_controls,
            missing_required_controls=missing_required,
            selector_health=selector_health,
        )


class HHIdentifierPage(BasePageObject):
    def is_active(self) -> bool:
        return self.resolver.find_first(self.selectors.login.identifier_email) is not None or self.resolver.find_first(self.selectors.login.identifier_phone) is not None

    def fill_identifier(self, *, identifier: str, identifier_type: IdentifierType) -> None:
        queries = self.selectors.login.identifier_phone if identifier_type == "phone" else self.selectors.login.identifier_email
        locator = self.resolver.find_first(queries)
        if locator is None:
            raise NormalizedAutomationError(
                AutomationErrorCode.SELECTOR_NOT_FOUND,
                "Unable to find HH identifier input",
                debug_summary=self._summary(),
            )

        self.actions.run(action="fill_identifier", callback=lambda: locator.fill(identifier), debug_summary=lambda: self._summary())

    def submit_identifier(self) -> None:
        locator = self.resolver.find_first(self.selectors.login.continue_button) or self.resolver.find_first(self.selectors.login.submit_button)
        if locator is None:
            raise NormalizedAutomationError(
                AutomationErrorCode.SELECTOR_NOT_FOUND,
                "Unable to find HH continue button",
                debug_summary=self._summary(),
            )

        self.actions.run(action="submit_identifier", callback=locator.click, debug_summary=lambda: self._summary())


class HHPasswordPage(BasePageObject):
    def is_active(self) -> bool:
        return self.resolver.find_first(self.selectors.login.password_input) is not None

    def fill_password(self, *, password: str) -> None:
        locator = self.resolver.find_first(self.selectors.login.password_input)
        if locator is None:
            raise NormalizedAutomationError(
                AutomationErrorCode.SELECTOR_NOT_FOUND,
                "Unable to find HH password input",
                debug_summary=self._summary(),
            )
        self.actions.run(action="fill_password", callback=lambda: locator.fill(password), debug_summary=lambda: self._summary())

    def submit_password(self) -> None:
        locator = self.resolver.find_first(self.selectors.login.submit_button)
        if locator is None:
            raise NormalizedAutomationError(
                AutomationErrorCode.SELECTOR_NOT_FOUND,
                "Unable to find HH submit button",
                debug_summary=self._summary(),
            )
        self.actions.run(action="submit_password", callback=locator.click, debug_summary=lambda: self._summary())


class HHCodePage(BasePageObject):
    def is_active(self) -> bool:
        return self.resolver.find_first(self.selectors.login.code_input) is not None

    def fill_code(self, *, code: str) -> None:
        locator = self.resolver.find_first(self.selectors.login.code_input)
        if locator is None:
            raise NormalizedAutomationError(
                AutomationErrorCode.SELECTOR_NOT_FOUND,
                "Unable to find HH OTP code input",
                debug_summary=self._summary(),
            )
        self.actions.run(action="fill_code", callback=lambda: locator.fill(code), debug_summary=lambda: self._summary())

    def submit_code(self) -> None:
        locator = self.resolver.find_first(self.selectors.login.submit_button)
        if locator is None:
            raise NormalizedAutomationError(
                AutomationErrorCode.SELECTOR_NOT_FOUND,
                "Unable to find HH submit button",
                debug_summary=self._summary(),
            )
        self.actions.run(action="submit_code", callback=locator.click, debug_summary=lambda: self._summary())


class HHAuthenticatedPage(BasePageObject):
    def is_active(self) -> bool:
        if "/applicant" in self.page.url or "/resume" in self.page.url:
            return True
        return self.resolver.find_first(self.selectors.login.authenticated_markers) is not None


class ApplicantHomePage(BasePageObject):
    def is_active(self) -> bool:
        if "/applicant" in self.page.url and "/resumes" not in self.page.url:
            return True
        return self.resolver.find_first(self.selectors.applicant_home.home_markers) is not None

    def capabilities(self) -> dict[str, Any]:
        return self._summary(
            page_detected=self.is_active(),
            key_controls={
                "resumes_nav_available": self.resolver.find_first(self.selectors.applicant_home.resumes_nav) is not None,
                "profile_surface_present": self.resolver.find_first(self.selectors.applicant_home.home_markers) is not None,
            },
        )

    def readiness_report(self) -> dict[str, Any]:
        return self._selector_report(
            page_name="applicant_home",
            required_controls={"home_markers": self.selectors.applicant_home.home_markers},
            optional_controls={"resumes_nav": self.selectors.applicant_home.resumes_nav},
        )

    def go_to_resumes(self) -> None:
        resume_nav = self.resolver.find_first(self.selectors.applicant_home.resumes_nav)
        if resume_nav is not None:
            self.actions.run(action="go_to_resumes_click", callback=resume_nav.click, debug_summary=lambda: self.capabilities())
            return

        self.actions.run(
            action="go_to_resumes_direct",
            callback=lambda: self.page.goto("https://hh.ru/applicant/resumes"),
            debug_summary=lambda: self.capabilities(),
        )


class ResumesListPage(BasePageObject):
    def is_active(self) -> bool:
        if "/applicant/resumes" in self.page.url:
            return True
        return self.resolver.find_first(self.selectors.resumes_list.list_markers) is not None

    def list_resume_entries_count(self) -> int:
        return self.resolver.count_first(self.selectors.resumes_list.resume_cards)

    def capabilities(self) -> dict[str, Any]:
        count = self.list_resume_entries_count()
        return self._summary(
            page_detected=self.is_active(),
            key_controls={
                "resume_entries_present": count > 0,
                "resume_entries_count": count,
                "create_resume_available": self.resolver.find_first(self.selectors.resumes_list.create_resume) is not None,
                "resume_edit_entry_available": self.resolver.find_first(self.selectors.resumes_list.edit_resume) is not None,
                "show_more_available": self.resolver.find_first(self.selectors.resumes_list.show_more) is not None,
                "actions_menu_available": self.resolver.find_first(self.selectors.resumes_list.resume_actions_menu) is not None,
            },
        )

    def readiness_report(self) -> dict[str, Any]:
        return self._selector_report(
            page_name="resumes_list",
            required_controls={"list_markers": self.selectors.resumes_list.list_markers},
            optional_controls={
                "resume_cards": self.selectors.resumes_list.resume_cards,
                "create_resume": self.selectors.resumes_list.create_resume,
                "edit_resume": self.selectors.resumes_list.edit_resume,
                "show_more": self.selectors.resumes_list.show_more,
                "resume_actions_menu": self.selectors.resumes_list.resume_actions_menu,
                "visibility_menu_entry": self.selectors.resumes_list.visibility_menu_entry,
                "visibility_dialog_markers": self.selectors.resumes_list.visibility_dialog_markers,
            },
        )

    def expand_more_if_available(self) -> bool:
        more = self.resolver.find_first(self.selectors.resumes_list.show_more)
        if more is None:
            return False
        self.actions.run(action="resumes_show_more", callback=more.click, debug_summary=lambda: self.capabilities())
        self.page.wait_for_timeout(300)
        return True

    def open_first_actions_menu(self) -> bool:
        menu = self.resolver.find_first(self.selectors.resumes_list.resume_actions_menu)
        if menu is None:
            return False
        self.actions.run(action="open_resume_actions_menu", callback=menu.click, debug_summary=lambda: self.capabilities())
        self.page.wait_for_timeout(200)
        return True

    def open_visibility_controls_from_menu(self) -> bool:
        item = self.resolver.find_first(self.selectors.resumes_list.visibility_menu_entry)
        if item is None:
            return False
        self.actions.run(action="open_visibility_controls", callback=item.click, debug_summary=lambda: self.capabilities())
        self.page.wait_for_timeout(250)
        return True

    def visibility_dialog_detected(self) -> bool:
        return self.resolver.find_first(self.selectors.resumes_list.visibility_dialog_markers) is not None

    def detect_visibility_mode(self) -> str:
        if self.resolver.find_first(self.selectors.resumes_list.visibility_hidden_markers) is not None:
            return "hidden_from_all"
        if self.resolver.find_first(self.selectors.resumes_list.visibility_public_markers) is not None:
            return "public_default"
        return "unknown"

    def select_hide_from_all(self) -> bool:
        option = self.resolver.find_first(self.selectors.resumes_list.visibility_hide_from_all)
        if option is None:
            return False
        self.actions.run(action="select_hide_from_all", callback=option.click, debug_summary=lambda: self.capabilities())
        self.page.wait_for_timeout(200)
        return True

    def save_visibility(self) -> bool:
        save = self.resolver.find_first(self.selectors.resumes_list.visibility_save)
        if save is None:
            return False
        self.actions.run(action="save_visibility", callback=save.click, debug_summary=lambda: self.capabilities())
        self.page.wait_for_timeout(350)
        return True

    def visibility_success_detected(self) -> bool:
        return self.resolver.find_first(self.selectors.resumes_list.visibility_success) is not None


class ResumeEditorPage(BasePageObject):
    def is_active(self) -> bool:
        if "/resume/" in self.page.url and ("/edit" in self.page.url or "/create" in self.page.url or "/new" in self.page.url):
            return True
        return self.resolver.find_first(self.selectors.resume_editor.editor_markers) is not None

    def capabilities(self) -> dict[str, Any]:
        return self._summary(
            page_detected=self.is_active(),
            key_controls={
                "section_controls_present": self.resolver.find_first(self.selectors.resume_editor.section_markers) is not None,
                "visibility_controls_present": self.resolver.find_first(self.selectors.resume_editor.visibility_controls) is not None,
                "save_controls_present": self.resolver.find_first(self.selectors.resume_editor.save_controls) is not None,
            },
        )

    def readiness_report(self) -> dict[str, Any]:
        return self._selector_report(
            page_name="resume_editor",
            required_controls={"editor_markers": self.selectors.resume_editor.editor_markers},
            optional_controls={
                "section_markers": self.selectors.resume_editor.section_markers,
                "visibility_controls": self.selectors.resume_editor.visibility_controls,
                "save_controls": self.selectors.resume_editor.save_controls,
            },
        )


class VacancyPage(BasePageObject):
    def is_active(self) -> bool:
        if "/vacancy/" in self.page.url:
            return True
        return self.resolver.find_first(self.selectors.vacancy.vacancy_markers) is not None

    def capabilities(self) -> dict[str, Any]:
        return self._summary(
            page_detected=self.is_active(),
            key_controls={
                "company_block_present": self.resolver.find_first(self.selectors.vacancy.company_markers) is not None,
                "apply_available": self.resolver.find_first(self.selectors.vacancy.apply_entry) is not None,
            },
        )

    def open_apply_surface(self) -> None:
        apply_entry = self.resolver.find_first(self.selectors.vacancy.apply_entry)
        if apply_entry is None:
            raise NormalizedAutomationError(
                AutomationErrorCode.SELECTOR_NOT_FOUND,
                "Unable to find HH apply/respond entry point",
                debug_summary=self.capabilities(),
            )
        self.actions.run(action="open_apply_surface", callback=apply_entry.click, debug_summary=lambda: self.capabilities())

    def readiness_report(self) -> dict[str, Any]:
        return self._selector_report(
            page_name="vacancy",
            required_controls={"vacancy_markers": self.selectors.vacancy.vacancy_markers},
            optional_controls={
                "apply_entry": self.selectors.vacancy.apply_entry,
                "company_markers": self.selectors.vacancy.company_markers,
            },
        )


class VacancyApplyPage(BasePageObject):
    def is_active(self) -> bool:
        if "/applicant/vacancy_response" in self.page.url:
            return True
        return self.resolver.find_first(self.selectors.apply_surface.surface_markers) is not None

    def capabilities(self) -> dict[str, Any]:
        return self._summary(
            page_detected=self.is_active(),
            key_controls={
                "resume_selector_present": self.resolver.find_first(self.selectors.apply_surface.resume_selector) is not None,
                "cover_letter_input_present": self.resolver.find_first(self.selectors.apply_surface.cover_letter_input) is not None,
                "final_submit_present": self.resolver.find_first(self.selectors.apply_surface.submit_controls) is not None,
            },
        )

    def readiness_report(self) -> dict[str, Any]:
        return self._selector_report(
            page_name="vacancy_apply_surface",
            required_controls={"surface_markers": self.selectors.apply_surface.surface_markers},
            optional_controls={
                "resume_selector": self.selectors.apply_surface.resume_selector,
                "cover_letter_input": self.selectors.apply_surface.cover_letter_input,
                "submit_controls": self.selectors.apply_surface.submit_controls,
            },
        )


def maybe_capture_screenshot_on_failure(page: BrowserPage, *, prefix: str) -> str | None:
    screenshot_dir = os.getenv("HH_AUTOMATION_SCREENSHOT_DIR")
    if not screenshot_dir:
        return None
    if not hasattr(page, "screenshot"):
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{prefix}_{timestamp}.png".replace("/", "_").replace(" ", "_")
    path = Path(screenshot_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    target = path / filename
    page.screenshot(path=str(target), full_page=True)
    return str(target)


class HHNavigationHelper:
    def __init__(self, *, page: BrowserPage, selectors: SelectorRegistry = DEFAULT_SELECTORS, action_runner: SafeActionRunner | None = None) -> None:
        self.page = page
        self.resolver = LocatorResolver(page)
        self.actions = action_runner or SafeActionRunner()
        self.selectors = selectors
        self.authenticated_page = HHAuthenticatedPage(page=page, selectors=selectors, resolver=self.resolver, actions=self.actions)
        self.applicant_home = ApplicantHomePage(page=page, selectors=selectors, resolver=self.resolver, actions=self.actions)
        self.resumes_page = ResumesListPage(page=page, selectors=selectors, resolver=self.resolver, actions=self.actions)
        self.resume_editor_page = ResumeEditorPage(page=page, selectors=selectors, resolver=self.resolver, actions=self.actions)
        self.vacancy_page = VacancyPage(page=page, selectors=selectors, resolver=self.resolver, actions=self.actions)
        self.apply_page = VacancyApplyPage(page=page, selectors=selectors, resolver=self.resolver, actions=self.actions)

    def ensure_authenticated_landing(self) -> dict[str, Any]:
        authenticated = self.authenticated_page.is_active() or self.applicant_home.is_active() or self.resumes_page.is_active()
        report = {
            "page_detected": authenticated,
            "key_controls": {
                "authenticated": authenticated,
                "applicant_home_detected": self.applicant_home.is_active(),
                "resumes_page_detected": self.resumes_page.is_active(),
            },
            "url": self.page.url,
            "title": self.page.title(),
        }
        return report

    def require_authenticated_landing(self) -> dict[str, Any]:
        report = self.ensure_authenticated_landing()
        if not report["page_detected"]:
            raise NormalizedAutomationError(
                AutomationErrorCode.AUTH_STATE_UNKNOWN,
                "Unable to confirm authenticated HH state",
                debug_summary=report,
            )
        return report

    def detect_current_page(self) -> dict[str, Any]:
        candidates = (
            ("apply_surface", self.apply_page.readiness_report()),
            ("vacancy", self.vacancy_page.readiness_report()),
            ("resume_editor", self.resume_editor_page.readiness_report()),
            ("resumes_list", self.resumes_page.readiness_report()),
            ("applicant_home", self.applicant_home.readiness_report()),
        )
        for page_name, report in candidates:
            if report["page_detected"]:
                return {
                    "current_detected_page": page_name,
                    "report": report,
                }
        return {
            "current_detected_page": "unknown",
            "report": self._unknown_page_report(),
        }

    def selector_health_summary(self) -> dict[str, Any]:
        return {
            "current_detected_page": self.detect_current_page()["current_detected_page"],
            "pages": {
                "applicant_home": self.applicant_home.readiness_report(),
                "resumes_list": self.resumes_page.readiness_report(),
                "resume_editor": self.resume_editor_page.readiness_report(),
                "vacancy": self.vacancy_page.readiness_report(),
                "apply_surface": self.apply_page.readiness_report(),
            },
        }

    def go_to_resumes(self) -> dict[str, Any]:
        self.applicant_home.go_to_resumes()
        capabilities = self.resumes_page.capabilities()
        if not capabilities["page_detected"]:
            raise NormalizedAutomationError(
                AutomationErrorCode.RESUME_SURFACE_NOT_AVAILABLE,
                "Resumes surface is not available after navigation",
                debug_summary=self.resumes_page.readiness_report(),
            )
        return capabilities

    def open_vacancy(self, vacancy_url: str) -> dict[str, Any]:
        self.actions.run(action="open_vacancy", callback=lambda: self.page.goto(vacancy_url), debug_summary=lambda: self.vacancy_page.capabilities())
        capabilities = self.vacancy_page.capabilities()
        if not capabilities["page_detected"]:
            raise NormalizedAutomationError(
                AutomationErrorCode.UNEXPECTED_NAVIGATION,
                "Vacancy page was not detected after navigation",
                debug_summary=self.vacancy_page.readiness_report(),
            )
        return capabilities

    def open_apply_surface(self) -> dict[str, Any]:
        self.vacancy_page.open_apply_surface()
        capabilities = self.apply_page.capabilities()
        if not capabilities["page_detected"]:
            raise NormalizedAutomationError(
                AutomationErrorCode.APPLY_SURFACE_NOT_AVAILABLE,
                "Apply surface did not appear after clicking apply entry",
                debug_summary=self.apply_page.readiness_report(),
            )
        return capabilities

    def _unknown_page_report(self) -> dict[str, Any]:
        return {
            "page": "unknown",
            "page_detected": False,
            "url": self.page.url,
            "title": self.page.title(),
            "primary_selectors_matched": {},
            "fallback_selectors_used": [],
            "missing_required_controls": ["known_page_markers"],
            "selector_health": {},
        }


class HHLoginFlowPageModel:
    def __init__(
        self,
        *,
        page: BrowserPage,
        selectors: SelectorRegistry = DEFAULT_SELECTORS,
        action_runner: SafeActionRunner | None = None,
    ) -> None:
        self.page = page
        self.selectors = selectors
        self.resolver = LocatorResolver(page)
        self.action_runner = action_runner or SafeActionRunner()
        self.identifier_page = HHIdentifierPage(page=page, selectors=selectors, resolver=self.resolver, actions=self.action_runner)
        self.password_page = HHPasswordPage(page=page, selectors=selectors, resolver=self.resolver, actions=self.action_runner)
        self.code_page = HHCodePage(page=page, selectors=selectors, resolver=self.resolver, actions=self.action_runner)
        self.authenticated_page = HHAuthenticatedPage(page=page, selectors=selectors, resolver=self.resolver, actions=self.action_runner)

    def detect_step(self) -> StepDetectionResult:
        if self.authenticated_page.is_active():
            return StepDetectionResult("authenticated", self.safe_summary())

        if self.password_page.is_active():
            return StepDetectionResult("password", self.safe_summary())

        if self.code_page.is_active():
            return StepDetectionResult("code", self.safe_summary())

        if self.identifier_page.is_active():
            return StepDetectionResult("identifier", self.safe_summary())

        password_entry = self.resolver.find_first(self.selectors.login.password_entry_button)
        if password_entry is not None:
            self.action_runner.run(action="switch_to_password", callback=password_entry.click, debug_summary=self.safe_summary)
            self.page.wait_for_timeout(350)
            if self.password_page.is_active():
                return StepDetectionResult("password", self.safe_summary())

        return StepDetectionResult("unknown", self.safe_summary())

    def fill_identifier(self, *, identifier: str, identifier_type: IdentifierType) -> None:
        self.identifier_page.fill_identifier(identifier=identifier, identifier_type=identifier_type)

    def submit_identifier(self) -> None:
        self.identifier_page.submit_identifier()

    def fill_password(self, *, password: str) -> None:
        self.password_page.fill_password(password=password)

    def submit_password(self) -> None:
        self.password_page.submit_password()

    def fill_code(self, *, code: str) -> None:
        self.code_page.fill_code(code=code)

    def submit_code(self) -> None:
        self.code_page.submit_code()

    def safe_summary(self) -> dict[str, Any]:
        return {
            "url": self.page.url,
            "title": self.page.title(),
            "has_identifier_input": self.identifier_page.is_active(),
            "has_password_input": self.password_page.is_active(),
            "has_code_input": self.code_page.is_active(),
            "authenticated": self.authenticated_page.is_active(),
        }

    def diagnostics_report(self) -> dict[str, Any]:
        detection = self.detect_step()
        return {
            "current_detected_step": detection.step_code,
            "summary": detection.summary,
            "selector_health": {
                "identifier_email": self.identifier_page._selector_report(
                    page_name="identifier",
                    required_controls={"identifier_email": self.selectors.login.identifier_email},
                ),
                "identifier_phone": self.identifier_page._selector_report(
                    page_name="identifier",
                    required_controls={"identifier_phone": self.selectors.login.identifier_phone},
                ),
                "password": self.password_page._selector_report(
                    page_name="password",
                    required_controls={"password_input": self.selectors.login.password_input},
                    optional_controls={"submit_button": self.selectors.login.submit_button},
                ),
                "code": self.code_page._selector_report(
                    page_name="code",
                    required_controls={"code_input": self.selectors.login.code_input},
                    optional_controls={"submit_button": self.selectors.login.submit_button},
                ),
            },
        }

    def ensure_step_detected(self) -> StepDetectionResult:
        result = self.detect_step()
        if result.step_code == "unknown":
            screenshot_path = maybe_capture_screenshot_on_failure(self.page, prefix="step_unknown")
            debug_summary = self.safe_summary()
            if screenshot_path is not None:
                debug_summary["screenshot_path"] = screenshot_path
            raise NormalizedAutomationError(
                AutomationErrorCode.PAGE_NOT_RECOGNIZED,
                "Unable to recognize current HH login step",
                debug_summary=debug_summary,
            )
        return result


def to_legacy_step(step_code: StepCode) -> Literal["awaiting_identifier", "awaiting_password", "awaiting_code", "connected", "failed"]:
    mapping = {
        "identifier": "awaiting_identifier",
        "password": "awaiting_password",
        "code": "awaiting_code",
        "authenticated": "connected",
        "unknown": "failed",
    }
    return mapping[step_code]
