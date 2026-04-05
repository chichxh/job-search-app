from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.db.models import HHBrowserConnection, HHManagedResume
from app.services.hh_resume_visibility_automation import PlaywrightResumeVisibilityAutomationClient
from app.services.hh_resume_visibility_service import HHResumeVisibilityAutomationError


@dataclass
class FakeLocator:
    key: str
    page: "FakePage"

    @property
    def first(self) -> "FakeLocator":
        return self

    def count(self) -> int:
        return self.page.visible.get(self.key, 0)

    def fill(self, value: str) -> None:
        self.page.filled.append((self.key, value))

    def click(self) -> None:
        self.page.clicked.append(self.key)
        self.page.handle_click(self.key)


@dataclass
class FakePage:
    url: str = "https://hh.ru/applicant/resumes"
    page_title: str = "HH Resumes"
    visible: dict[str, int] = field(default_factory=dict)
    clicked: list[str] = field(default_factory=list)
    filled: list[tuple[str, str]] = field(default_factory=list)
    waits: list[int] = field(default_factory=list)
    navigated: list[str] = field(default_factory=list)

    def title(self) -> str:
        return self.page_title

    def goto(self, url: str) -> None:
        self.navigated.append(url)
        self.url = url

    def _make(self, key: str) -> FakeLocator:
        return FakeLocator(key=key, page=self)

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
        return

    def handle_click(self, key: str) -> None:
        if key in {"role:button:Подробнее", "text:Подробнее"}:
            self.visible["css:a[href*='/resume/abc123']"] = 1
            self.visible["css:[data-qa*='resume-actions']"] = 1
        if key == "css:[data-qa*='resume-actions']":
            self.visible["text:Изменить видимость"] = 1
        if key == "text:Изменить видимость":
            self.visible["text:Видимость резюме"] = 1
            self.visible["text:Видно всем работодателям"] = 1
            self.visible["text:Просто скрыть от всех"] = 1
            self.visible["role:button:Сохранить"] = 1
        if key == "text:Просто скрыть от всех":
            self.visible["text:Скрыто от всех"] = 1
        if key == "role:button:Сохранить":
            self.visible["text:Изменения сохранены"] = 1


@dataclass
class FakeRuntime:
    page: FakePage

    def close(self) -> None:
        return


class FakeSessionStorage:
    def load(self, *, ref: str) -> dict:
        return {"ref": ref}


class RuntimeFactory:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    def __call__(self, storage_state: dict) -> FakeRuntime:
        return FakeRuntime(page=self.page)


def _managed_resume(*, external_id: str = "abc123", title: str = "Backend Engineer") -> HHManagedResume:
    return HHManagedResume(id=10, user_id=1, profile_id=1, hh_resume_external_id=external_id, hh_resume_url=f"https://hh.ru/resume/{external_id}", title=title)


def _connection() -> HHBrowserConnection:
    return HHBrowserConnection(user_id=1, status="connected", session_state_ref="local://u1.json", requires_reauth=False)


def test_visibility_check_single_resume_path() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='resume-list']": 1,
            "css:a[href*='/resume/abc123']": 1,
            "css:[data-qa*='resume-actions']": 1,
        }
    )
    client = PlaywrightResumeVisibilityAutomationClient(
        session_storage=FakeSessionStorage(),
        runtime_factory=RuntimeFactory(page),
    )

    result = client.detect_visibility(user_id=1, connection=_connection(), managed_resume=_managed_resume())

    assert result.current_visibility_mode == "public_default"
    assert "css:[data-qa*='resume-actions']" in page.clicked
    assert "text:Изменить видимость" in page.clicked


def test_visibility_check_multiple_resumes_with_show_more() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='resume-list']": 1,
            "role:button:Подробнее": 1,
        }
    )
    client = PlaywrightResumeVisibilityAutomationClient(
        session_storage=FakeSessionStorage(),
        runtime_factory=RuntimeFactory(page),
    )

    result = client.detect_visibility(user_id=1, connection=_connection(), managed_resume=_managed_resume())

    assert result.current_visibility_mode == "public_default"
    assert "role:button:Подробнее" in page.clicked


def test_visibility_dialog_detection_and_hide_from_all_save_path() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='resume-list']": 1,
            "css:a[href*='/resume/abc123']": 1,
            "css:[data-qa*='resume-actions']": 1,
        }
    )
    client = PlaywrightResumeVisibilityAutomationClient(
        session_storage=FakeSessionStorage(),
        runtime_factory=RuntimeFactory(page),
    )

    result = client.hide_from_all(user_id=1, connection=_connection(), managed_resume=_managed_resume())

    assert result.current_visibility_mode == "hidden_from_all"
    assert "text:Просто скрыть от всех" in page.clicked
    assert "role:button:Сохранить" in page.clicked


def test_normalized_error_on_unknown_visibility_layout() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='resume-list']": 1,
            "css:a[href*='/resume/abc123']": 1,
            "css:[data-qa*='resume-actions']": 1,
            "text:Изменить видимость": 1,
            "text:Видимость резюме": 1,
            "text:Просто скрыть от всех": 1,
            "role:button:Сохранить": 1,
        }
    )

    def _no_success_click(key: str) -> None:
        if key == "css:[data-qa*='resume-actions']":
            page.visible["text:Изменить видимость"] = 1
        if key == "text:Изменить видимость":
            page.visible["text:Видимость резюме"] = 1
            page.visible["text:Просто скрыть от всех"] = 1
            page.visible["role:button:Сохранить"] = 1

    page.handle_click = _no_success_click  # type: ignore[assignment]

    client = PlaywrightResumeVisibilityAutomationClient(
        session_storage=FakeSessionStorage(),
        runtime_factory=RuntimeFactory(page),
    )

    with pytest.raises(HHResumeVisibilityAutomationError) as exc:
        client.hide_from_all(user_id=1, connection=_connection(), managed_resume=_managed_resume())

    assert exc.value.code == "VISIBILITY_POST_SAVE_VERIFY_FAILED"
