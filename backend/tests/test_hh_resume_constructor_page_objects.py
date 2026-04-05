from __future__ import annotations

from dataclasses import dataclass, field

from app.services.hh_resume_constructor_page_objects import HHResumeConstructorPageModel


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


@dataclass
class FakePage:
    url: str = "https://hh.ru/applicant/resumes"
    page_title: str = "HH"
    visible: dict[str, int] = field(default_factory=dict)
    filled: list[tuple[str, str]] = field(default_factory=list)
    clicked: list[str] = field(default_factory=list)

    def title(self) -> str:
        return self.page_title

    def goto(self, url: str) -> None:
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
        return None


def test_profession_step_fill_prefers_exact_suggestion() -> None:
    page = FakePage(
        visible={
            "label:Профессия": 1,
            "text:Backend Engineer": 1,
        }
    )
    model = HHResumeConstructorPageModel(page=page)

    model.fill_profession("Backend Engineer")

    assert ("label:Профессия", "Backend Engineer") in page.filled
    assert "text:Backend Engineer" in page.clicked


def test_optional_step_skip_uses_skip_control() -> None:
    page = FakePage(visible={"text:Пропустить": 1})
    model = HHResumeConstructorPageModel(page=page)

    model.fill_education_minimum([])

    assert "text:Пропустить" in page.clicked
