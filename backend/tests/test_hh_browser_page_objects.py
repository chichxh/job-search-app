from __future__ import annotations

from dataclasses import dataclass, field

from app.services.hh_browser_error_taxonomy import AutomationErrorCode
from app.services.hh_browser_page_objects import (
    HHLoginFlowPageModel,
    HHNavigationHelper,
    NormalizedAutomationError,
    maybe_capture_screenshot_on_failure,
    to_legacy_step,
)


@dataclass
class FakeLocator:
    key: str
    count_value: int
    page: "FakePage"

    @property
    def first(self) -> "FakeLocator":
        return self

    def count(self) -> int:
        return self.count_value

    def fill(self, value: str) -> None:
        self.page.filled.append((self.key, value))

    def click(self) -> None:
        self.page.clicked.append(self.key)
        if self.key == "role:button:Войти с паролем":
            self.page.visible["label:Пароль"] = 1


@dataclass
class FakePage:
    url: str = "https://hh.ru/account/login"
    page_title: str = "HH Login"
    visible: dict[str, int] = field(default_factory=dict)
    filled: list[tuple[str, str]] = field(default_factory=list)
    clicked: list[str] = field(default_factory=list)
    waits: list[int] = field(default_factory=list)
    navigated: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)

    def title(self) -> str:
        return self.page_title

    def goto(self, url: str) -> None:
        self.navigated.append(url)
        self.url = url

    def _make(self, key: str) -> FakeLocator:
        return FakeLocator(key=key, count_value=self.visible.get(key, 0), page=self)

    def get_by_role(self, role: str, *, name: str) -> FakeLocator:
        return self._make(f"role:{role}:{name}")

    def get_by_label(self, text: str) -> FakeLocator:
        return self._make(f"label:{text}")

    def get_by_text(self, text: str) -> FakeLocator:
        return self._make(f"text:{text}")

    def locator(self, selector: str) -> FakeLocator:
        return self._make(f"css:{selector}")

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.waits.append(timeout_ms)

    def screenshot(self, *, path: str, full_page: bool = True) -> None:
        self.screenshots.append(path)


def test_detect_identifier_step() -> None:
    page = FakePage(visible={"label:Почта": 1})
    flow = HHLoginFlowPageModel(page=page)

    result = flow.detect_step()

    assert result.step_code == "identifier"
    assert to_legacy_step(result.step_code) == "awaiting_identifier"


def test_detect_password_step() -> None:
    page = FakePage(visible={"label:Пароль": 1})
    flow = HHLoginFlowPageModel(page=page)

    assert flow.detect_step().step_code == "password"


def test_detect_code_step() -> None:
    page = FakePage(visible={"label:Код": 1})
    flow = HHLoginFlowPageModel(page=page)

    assert flow.detect_step().step_code == "code"


def test_detect_authenticated_step_by_url() -> None:
    page = FakePage(url="https://hh.ru/applicant/resumes")
    flow = HHLoginFlowPageModel(page=page)

    assert flow.detect_step().step_code == "authenticated"


def test_unknown_step_mapping() -> None:
    page = FakePage(visible={})
    flow = HHLoginFlowPageModel(page=page)

    result = flow.detect_step()

    assert result.step_code == "unknown"
    assert to_legacy_step(result.step_code) == "failed"


def test_selector_fallback_for_identifier_uses_css() -> None:
    page = FakePage(visible={"css:input[type='email']": 1})
    flow = HHLoginFlowPageModel(page=page)

    flow.fill_identifier(identifier="user@example.com", identifier_type="email")

    assert page.filled == [("css:input[type='email']", "user@example.com")]


def test_action_methods_use_expected_locators() -> None:
    page = FakePage(
        visible={
            "label:Почта": 1,
            "role:button:Дальше": 1,
            "label:Пароль": 1,
            "role:button:Войти": 1,
            "label:Код": 1,
        }
    )
    flow = HHLoginFlowPageModel(page=page)

    flow.fill_identifier(identifier="user@example.com", identifier_type="email")
    flow.submit_identifier()
    flow.fill_password(password="secret")
    flow.submit_password()
    flow.fill_code(code="1234")
    flow.submit_code()

    assert ("label:Почта", "user@example.com") in page.filled
    assert ("label:Пароль", "secret") in page.filled
    assert ("label:Код", "1234") in page.filled
    assert "role:button:Дальше" in page.clicked
    assert "role:button:Войти" in page.clicked


def test_password_entry_fallback_button_switches_state() -> None:
    page = FakePage(visible={"role:button:Войти с паролем": 1})
    flow = HHLoginFlowPageModel(page=page)

    result = flow.detect_step()

    assert result.step_code == "password"
    assert "role:button:Войти с паролем" in page.clicked


def test_resumes_page_capabilities_include_create_and_count() -> None:
    page = FakePage(
        url="https://hh.ru/applicant/resumes",
        visible={
            "css:[data-qa='resume-card']": 2,
            "role:button:Создать резюме": 1,
            "text:Редактировать": 1,
        },
    )
    helper = HHNavigationHelper(page=page)

    capabilities = helper.resumes_page.capabilities()

    assert capabilities["page_detected"] is True
    assert capabilities["key_controls"]["resume_entries_count"] == 2
    assert capabilities["key_controls"]["create_resume_available"] is True
    assert capabilities["key_controls"]["resume_edit_entry_available"] is True


def test_resume_editor_visibility_detection_uses_fallback_selector() -> None:
    page = FakePage(
        url="https://hh.ru/resume/new",
        visible={
            "css:form[action*='/resume']": 1,
            "css:[data-qa*='resume-visibility']": 1,
            "css:button[type='submit']": 1,
        },
    )
    helper = HHNavigationHelper(page=page)

    editor_caps = helper.resume_editor_page.capabilities()

    assert editor_caps["page_detected"] is True
    assert editor_caps["key_controls"]["section_controls_present"] is False
    assert editor_caps["key_controls"]["visibility_controls_present"] is True
    assert editor_caps["key_controls"]["save_controls_present"] is True


def test_vacancy_and_apply_surface_detection() -> None:
    page = FakePage(
        url="https://hh.ru/vacancy/123",
        visible={
            "css:[data-qa='vacancy-title']": 1,
            "role:button:Откликнуться": 1,
            "css:[data-qa='vacancy-response-popup']": 1,
            "label:Резюме": 1,
            "label:Сопроводительное письмо": 1,
            "role:button:Отправить": 1,
        },
    )
    helper = HHNavigationHelper(page=page)

    vacancy_caps = helper.vacancy_page.capabilities()
    apply_caps = helper.apply_page.capabilities()

    assert vacancy_caps["page_detected"] is True
    assert vacancy_caps["key_controls"]["apply_available"] is True
    assert apply_caps["page_detected"] is True
    assert apply_caps["key_controls"]["resume_selector_present"] is True
    assert apply_caps["key_controls"]["cover_letter_input_present"] is True
    assert apply_caps["key_controls"]["final_submit_present"] is True


def test_vacancy_page_unavailable_detector() -> None:
    page = FakePage(
        url="https://hh.ru/vacancy/404",
        visible={
            "css:[data-qa='vacancy-title']": 1,
            "text:Вакансия в архиве": 1,
        },
    )
    helper = HHNavigationHelper(page=page)

    assert helper.vacancy_page.detect_unavailable() is True
    assert helper.vacancy_page.capabilities()["key_controls"]["vacancy_unavailable_detected"] is True


def test_apply_surface_state_detectors_cover_terminal_states() -> None:
    page = FakePage(
        url="https://hh.ru/vacancy/123",
        visible={
            "css:[data-qa='vacancy-response-popup']": 1,
            "text:Вы уже откликались": 1,
            "text:Отклик недоступен": 1,
            "text:Войдите на сайт": 1,
            "text:Ваш отклик отправлен": 1,
            "css:textarea[required]": 1,
        },
    )
    helper = HHNavigationHelper(page=page)

    assert helper.apply_page.detect_already_applied() is True
    assert helper.apply_page.detect_cannot_apply() is True
    assert helper.apply_page.detect_auth_lost() is True
    assert helper.apply_page.detect_success() is True
    assert helper.apply_page.is_cover_letter_required() is True


def test_navigation_helper_go_to_resumes_uses_click_then_goto_fallback() -> None:
    page_click = FakePage(visible={"text:Резюме": 1, "css:[data-qa='resume-list']": 1})
    helper_click = HHNavigationHelper(page=page_click)
    helper_click.go_to_resumes()
    assert "text:Резюме" in page_click.clicked

    page_goto = FakePage(visible={})
    helper_goto = HHNavigationHelper(page=page_goto)
    helper_goto.go_to_resumes()
    assert page_goto.navigated[-1] == "https://hh.ru/applicant/resumes"


def test_navigation_helper_open_vacancy_and_apply_orchestration() -> None:
    page = FakePage(visible={"role:button:Откликнуться": 1, "css:[data-qa='vacancy-response-popup']": 1})
    helper = HHNavigationHelper(page=page)

    helper.open_vacancy("https://hh.ru/vacancy/999")
    helper.open_apply_surface()

    assert page.navigated == ["https://hh.ru/vacancy/999"]
    assert "role:button:Откликнуться" in page.clicked


def test_login_diagnostics_report_includes_selector_health_and_fallback() -> None:
    page = FakePage(visible={"css:input[type='email']": 1})
    flow = HHLoginFlowPageModel(page=page)

    report = flow.diagnostics_report()

    email_health = report["selector_health"]["identifier_email"]["selector_health"]["identifier_email"]
    assert report["current_detected_step"] == "identifier"
    assert email_health["matched"] is True
    assert email_health["used_fallback"] is True
    assert email_health["matched_query"] == "css:input[type='email']"


def test_selector_health_summary_reports_missing_required_controls() -> None:
    page = FakePage(visible={})
    helper = HHNavigationHelper(page=page)

    summary = helper.selector_health_summary()

    assert summary["current_detected_page"] == "unknown"
    assert summary["pages"]["vacancy"]["missing_required_controls"] == ["vacancy_markers"]


def test_navigation_failures_map_to_taxonomy_codes() -> None:
    page_vacancy = FakePage(visible={})
    helper_vacancy = HHNavigationHelper(page=page_vacancy)
    try:
        helper_vacancy.open_vacancy("https://hh.ru/other/123")
        assert False, "Expected navigation failure"
    except NormalizedAutomationError as exc:
        assert exc.code == AutomationErrorCode.UNEXPECTED_NAVIGATION

    page_apply = FakePage(visible={"css:[data-qa='vacancy-title']": 1, "role:button:Откликнуться": 1})
    helper_apply = HHNavigationHelper(page=page_apply)
    try:
        helper_apply.open_apply_surface()
        assert False, "Expected apply failure"
    except NormalizedAutomationError as exc:
        assert exc.code == AutomationErrorCode.APPLY_SURFACE_NOT_AVAILABLE


def test_screenshot_hook_is_safe_and_does_not_leak_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HH_AUTOMATION_SCREENSHOT_DIR", str(tmp_path))
    page = FakePage(url="https://hh.ru/account/login?token=secret")

    screenshot_path = maybe_capture_screenshot_on_failure(page, prefix="submit_identifier failure")

    assert screenshot_path is not None
    assert "secret" not in screenshot_path
    assert page.screenshots and page.screenshots[0] == screenshot_path
