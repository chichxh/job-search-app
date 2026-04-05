from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol


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


@dataclass(frozen=True)
class SelectorQuery:
    strategy: Literal["role", "label", "text", "css"]
    value: str
    role: str | None = None


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
        # Primary/fallback strategy for login identifier.
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
        SelectorQuery("label", "Пароль"),
        SelectorQuery("css", "input[type='password']"),
        SelectorQuery("css", "input[name*='password']"),
        ),
        code_input=(
        SelectorQuery("label", "Код"),
        SelectorQuery("label", "Код из SMS"),
        SelectorQuery("label", "Код подтверждения"),
        SelectorQuery("css", "input[inputmode='numeric']"),
        SelectorQuery("css", "input[name*='otp']"),
        SelectorQuery("css", "input[name*='code']"),
        ),
        continue_button=(
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
        for query in queries:
            locator = self._resolve(query)
            if locator is None:
                continue
            if locator.count() > 0:
                return locator.first
        return None

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
                        "ACTION_FAILED",
                        f"Action failed: {action}",
                        debug_summary=debug_summary(),
                    ) from exc

        raise NormalizedAutomationError("ACTION_FAILED", f"Action failed: {action}", debug_summary=debug_summary())


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


class HHIdentifierPage(BasePageObject):
    def is_active(self) -> bool:
        return self.resolver.find_first(self.selectors.login.identifier_email) is not None or self.resolver.find_first(self.selectors.login.identifier_phone) is not None

    def fill_identifier(self, *, identifier: str, identifier_type: IdentifierType) -> None:
        queries = self.selectors.login.identifier_phone if identifier_type == "phone" else self.selectors.login.identifier_email
        locator = self.resolver.find_first(queries)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH identifier input", debug_summary=self._summary())

        self.actions.run(action="fill_identifier", callback=lambda: locator.fill(identifier), debug_summary=lambda: self._summary())

    def submit_identifier(self) -> None:
        locator = self.resolver.find_first(self.selectors.login.continue_button) or self.resolver.find_first(self.selectors.login.submit_button)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH continue button", debug_summary=self._summary())

        self.actions.run(action="submit_identifier", callback=locator.click, debug_summary=lambda: self._summary())


class HHPasswordPage(BasePageObject):
    def is_active(self) -> bool:
        return self.resolver.find_first(self.selectors.login.password_input) is not None

    def fill_password(self, *, password: str) -> None:
        locator = self.resolver.find_first(self.selectors.login.password_input)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH password input", debug_summary=self._summary())
        self.actions.run(action="fill_password", callback=lambda: locator.fill(password), debug_summary=lambda: self._summary())

    def submit_password(self) -> None:
        locator = self.resolver.find_first(self.selectors.login.submit_button)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH submit button", debug_summary=self._summary())
        self.actions.run(action="submit_password", callback=locator.click, debug_summary=lambda: self._summary())


class HHCodePage(BasePageObject):
    def is_active(self) -> bool:
        return self.resolver.find_first(self.selectors.login.code_input) is not None

    def fill_code(self, *, code: str) -> None:
        locator = self.resolver.find_first(self.selectors.login.code_input)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH OTP code input", debug_summary=self._summary())
        self.actions.run(action="fill_code", callback=lambda: locator.fill(code), debug_summary=lambda: self._summary())

    def submit_code(self) -> None:
        locator = self.resolver.find_first(self.selectors.login.submit_button)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH submit button", debug_summary=self._summary())
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
            },
        )


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
                "HH_SELECTOR_NOT_FOUND",
                "Unable to find HH apply/respond entry point",
                debug_summary=self.capabilities(),
            )
        self.actions.run(action="open_apply_surface", callback=apply_entry.click, debug_summary=lambda: self.capabilities())


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
        return {
            "page_detected": authenticated,
            "key_controls": {
                "authenticated": authenticated,
                "applicant_home_detected": self.applicant_home.is_active(),
                "resumes_page_detected": self.resumes_page.is_active(),
            },
            "url": self.page.url,
            "title": self.page.title(),
        }

    def go_to_resumes(self) -> dict[str, Any]:
        self.applicant_home.go_to_resumes()
        return self.resumes_page.capabilities()

    def open_vacancy(self, vacancy_url: str) -> dict[str, Any]:
        self.actions.run(action="open_vacancy", callback=lambda: self.page.goto(vacancy_url), debug_summary=lambda: self.vacancy_page.capabilities())
        return self.vacancy_page.capabilities()

    def open_apply_surface(self) -> dict[str, Any]:
        self.vacancy_page.open_apply_surface()
        return self.apply_page.capabilities()


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


def to_legacy_step(step_code: StepCode) -> Literal["awaiting_identifier", "awaiting_password", "awaiting_code", "connected", "failed"]:
    mapping = {
        "identifier": "awaiting_identifier",
        "password": "awaiting_password",
        "code": "awaiting_code",
        "authenticated": "connected",
        "unknown": "failed",
    }
    return mapping[step_code]
