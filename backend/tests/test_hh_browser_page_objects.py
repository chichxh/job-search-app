from __future__ import annotations

from dataclasses import dataclass, field

from app.services.hh_browser_page_objects import HHLoginFlowPageModel, to_legacy_step


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

    def title(self) -> str:
        return self.page_title

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
