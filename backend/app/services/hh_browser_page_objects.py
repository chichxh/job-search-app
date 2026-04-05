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
class SelectorRegistry:
    identifier_phone: tuple[SelectorQuery, ...]
    identifier_email: tuple[SelectorQuery, ...]
    password_input: tuple[SelectorQuery, ...]
    code_input: tuple[SelectorQuery, ...]
    continue_button: tuple[SelectorQuery, ...]
    submit_button: tuple[SelectorQuery, ...]
    password_entry_button: tuple[SelectorQuery, ...]
    authenticated_markers: tuple[SelectorQuery, ...]


DEFAULT_SELECTORS = SelectorRegistry(
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
        return self.resolver.find_first(self.selectors.identifier_email) is not None or self.resolver.find_first(self.selectors.identifier_phone) is not None

    def fill_identifier(self, *, identifier: str, identifier_type: IdentifierType) -> None:
        queries = self.selectors.identifier_phone if identifier_type == "phone" else self.selectors.identifier_email
        locator = self.resolver.find_first(queries)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH identifier input", debug_summary=self._summary())

        self.actions.run(action="fill_identifier", callback=lambda: locator.fill(identifier), debug_summary=lambda: self._summary())

    def submit_identifier(self) -> None:
        locator = self.resolver.find_first(self.selectors.continue_button) or self.resolver.find_first(self.selectors.submit_button)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH continue button", debug_summary=self._summary())

        self.actions.run(action="submit_identifier", callback=locator.click, debug_summary=lambda: self._summary())


class HHPasswordPage(BasePageObject):
    def is_active(self) -> bool:
        return self.resolver.find_first(self.selectors.password_input) is not None

    def fill_password(self, *, password: str) -> None:
        locator = self.resolver.find_first(self.selectors.password_input)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH password input", debug_summary=self._summary())
        self.actions.run(action="fill_password", callback=lambda: locator.fill(password), debug_summary=lambda: self._summary())

    def submit_password(self) -> None:
        locator = self.resolver.find_first(self.selectors.submit_button)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH submit button", debug_summary=self._summary())
        self.actions.run(action="submit_password", callback=locator.click, debug_summary=lambda: self._summary())


class HHCodePage(BasePageObject):
    def is_active(self) -> bool:
        return self.resolver.find_first(self.selectors.code_input) is not None

    def fill_code(self, *, code: str) -> None:
        locator = self.resolver.find_first(self.selectors.code_input)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH OTP code input", debug_summary=self._summary())
        self.actions.run(action="fill_code", callback=lambda: locator.fill(code), debug_summary=lambda: self._summary())

    def submit_code(self) -> None:
        locator = self.resolver.find_first(self.selectors.submit_button)
        if locator is None:
            raise NormalizedAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH submit button", debug_summary=self._summary())
        self.actions.run(action="submit_code", callback=locator.click, debug_summary=lambda: self._summary())


class HHAuthenticatedPage(BasePageObject):
    def is_active(self) -> bool:
        if "/applicant" in self.page.url or "/resume" in self.page.url:
            return True
        return self.resolver.find_first(self.selectors.authenticated_markers) is not None


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

        password_entry = self.resolver.find_first(self.selectors.password_entry_button)
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
