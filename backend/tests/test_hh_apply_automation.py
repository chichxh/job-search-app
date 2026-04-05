from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.services.hh_apply_automation import PlaywrightHHApplyAutomationClient
from app.services.hh_apply_service import HHApplyAutomationError


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
        action = self.page.click_actions.get(self.key)
        if action:
            action(self.page)


@dataclass
class FakePage:
    url: str = "https://hh.ru/applicant/resumes"
    page_title: str = "HH"
    visible: dict[str, int] = field(default_factory=dict)
    clicked: list[str] = field(default_factory=list)
    filled: list[tuple[str, str]] = field(default_factory=list)
    waits: list[int] = field(default_factory=list)
    navigated: list[str] = field(default_factory=list)
    click_actions: dict[str, callable] = field(default_factory=dict)

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


@dataclass
class FakeRuntime:
    page: FakePage

    def close(self) -> None:
        return


class FakeSessionStorage:
    def load(self, *, ref: str) -> dict:
        return {"ref": ref}


def _client(page: FakePage) -> PlaywrightHHApplyAutomationClient:
    return PlaywrightHHApplyAutomationClient(
        session_storage=FakeSessionStorage(),
        runtime_factory=lambda state: FakeRuntime(page=page),
    )


def _entities() -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    connection = SimpleNamespace(session_state_ref="session.json")
    apply_run = SimpleNamespace(id=7)
    managed_resume = SimpleNamespace(
        id=4,
        hh_resume_external_id="abc123",
        hh_resume_url="https://hh.ru/resume/abc123",
        title="Python Developer",
    )
    vacancy = SimpleNamespace(url="https://hh.ru/vacancy/123", external_ref="123")
    return connection, apply_run, managed_resume, vacancy


def test_apply_happy_path_with_resume_selection_and_cover_letter() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
            "role:button:Откликнуться": 1,
            "css:[data-qa='vacancy-response-popup']": 1,
            "label:Резюме": 1,
            "css:a[href*='/resume/abc123']": 1,
            "label:Сопроводительное письмо": 1,
            "role:button:Отправить": 1,
        }
    )
    page.click_actions["role:button:Отправить"] = lambda p: p.visible.__setitem__("text:Ваш отклик отправлен", 1)

    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()

    result = client.apply_to_vacancy(
        user_id=1,
        connection=connection,
        apply_run=apply_run,
        managed_resume=managed_resume,
        vacancy=vacancy,
        cover_letter_text="Короткое письмо",
        dry_run=False,
    )

    assert result.result_type == "submitted"
    assert "label:Сопроводительное письмо" in [k for k, _ in page.filled]
    assert "css:a[href*='/resume/abc123']" in page.clicked


def test_apply_single_resume_path_without_selector() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
            "role:button:Откликнуться": 1,
            "css:[data-qa='vacancy-response-popup']": 1,
            "role:button:Отправить": 1,
            "text:Отклик успешно отправлен": 1,
        }
    )
    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()

    result = client.apply_to_vacancy(
        user_id=1,
        connection=connection,
        apply_run=apply_run,
        managed_resume=managed_resume,
        vacancy=vacancy,
        cover_letter_text=None,
        dry_run=False,
    )

    assert result.result_type == "submitted"


def test_apply_cover_letter_required_without_text() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
            "role:button:Откликнуться": 1,
            "css:[data-qa='vacancy-response-popup']": 1,
            "label:Сопроводительное письмо": 1,
            "css:textarea[required]": 1,
            "role:button:Отправить": 1,
        }
    )
    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()

    with pytest.raises(HHApplyAutomationError) as exc:
        client.apply_to_vacancy(
            user_id=1,
            connection=connection,
            apply_run=apply_run,
            managed_resume=managed_resume,
            vacancy=vacancy,
            cover_letter_text=None,
            dry_run=False,
        )

    assert exc.value.code == "cover_letter_required"


def test_apply_resume_selection_uses_single_card_fallback() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
            "role:button:Откликнуться": 1,
            "css:[data-qa='vacancy-response-popup']": 1,
            "label:Резюме": 1,
            "css:[data-qa='resume-selector-item']": 1,
            "role:button:Отправить": 1,
            "text:Отклик успешно отправлен": 1,
        }
    )
    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()
    managed_resume.hh_resume_external_id = None
    managed_resume.hh_resume_url = None
    managed_resume.title = "Не совпадающий заголовок"

    result = client.apply_to_vacancy(
        user_id=1,
        connection=connection,
        apply_run=apply_run,
        managed_resume=managed_resume,
        vacancy=vacancy,
        cover_letter_text=None,
        dry_run=False,
    )

    assert result.result_type == "submitted"
    assert "css:[data-qa='resume-selector-item']" in page.clicked


def test_apply_already_applied_path() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
            "text:Вы уже откликались": 1,
        }
    )
    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()

    result = client.apply_to_vacancy(
        user_id=1,
        connection=connection,
        apply_run=apply_run,
        managed_resume=managed_resume,
        vacancy=vacancy,
        cover_letter_text=None,
        dry_run=False,
    )

    assert result.result_type == "already_applied"


def test_apply_auth_lost_in_apply_surface() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
            "role:button:Откликнуться": 1,
            "css:[data-qa='vacancy-response-popup']": 1,
            "text:Войдите на сайт": 1,
        }
    )
    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()

    with pytest.raises(HHApplyAutomationError) as exc:
        client.apply_to_vacancy(
            user_id=1,
            connection=connection,
            apply_run=apply_run,
            managed_resume=managed_resume,
            vacancy=vacancy,
            cover_letter_text="x",
            dry_run=False,
        )

    assert exc.value.code == "session_expired"


def test_apply_missing_submit_control_normalized() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
            "role:button:Откликнуться": 1,
            "css:[data-qa='vacancy-response-popup']": 1,
        }
    )
    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()

    with pytest.raises(HHApplyAutomationError) as exc:
        client.apply_to_vacancy(
            user_id=1,
            connection=connection,
            apply_run=apply_run,
            managed_resume=managed_resume,
            vacancy=vacancy,
            cover_letter_text=None,
            dry_run=False,
        )

    assert exc.value.code == "apply_submit_failed"


def test_apply_vacancy_unavailable_is_normalized() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
            "text:Вакансия в архиве": 1,
        }
    )
    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()

    with pytest.raises(HHApplyAutomationError) as exc:
        client.apply_to_vacancy(
            user_id=1,
            connection=connection,
            apply_run=apply_run,
            managed_resume=managed_resume,
            vacancy=vacancy,
            cover_letter_text=None,
            dry_run=False,
        )

    assert exc.value.code == "vacancy_page_unavailable"


def test_apply_entry_not_found_is_normalized() -> None:
    page = FakePage(
        visible={
            "css:[data-qa='applicant-dashboard']": 1,
            "css:[data-qa='vacancy-title']": 1,
        }
    )
    client = _client(page)
    connection, apply_run, managed_resume, vacancy = _entities()

    with pytest.raises(HHApplyAutomationError) as exc:
        client.apply_to_vacancy(
            user_id=1,
            connection=connection,
            apply_run=apply_run,
            managed_resume=managed_resume,
            vacancy=vacancy,
            cover_letter_text=None,
            dry_run=False,
        )

    assert exc.value.code == "apply_entry_not_found"
