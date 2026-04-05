from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.schemas.hh_browser_integration import HHTargetedResumePayload
from app.services.hh_targeted_resume_automation import PlaywrightTargetedResumeAutomationClient
from app.services.hh_targeted_resume_service import HHResumeAutomationError


@dataclass
class FakeConstructor:
    steps: list[str]
    index: int = 0
    calls: list[str] = field(default_factory=list)

    def detect_step(self) -> str:
        if self.index >= len(self.steps):
            return "success"
        step = self.steps[self.index]
        self.index += 1
        return step

    def fill_profession(self, profession_title: str) -> None:
        self.calls.append(f"profession:{profession_title}")

    def fill_main_info(self, *, title: str, summary: str) -> None:
        self.calls.append("main_info")

    def fill_education_minimum(self, education):
        self.calls.append("education")

    def fill_skills(self, skills):
        self.calls.append("skills")

    def fill_experience_minimum(self, experiences):
        self.calls.append("experience")

    def continue_next(self) -> None:
        self.calls.append("continue")

    def skip_or_continue(self, *, optional: bool) -> None:
        self.calls.append(f"skip:{optional}")

    def extract_success(self, fallback_title: str):
        return ("abc123", "https://hh.ru/resume/abc123", fallback_title)

    @property
    def page(self):
        class _Page:
            @staticmethod
            def wait_for_timeout(timeout_ms: int) -> None:
                return None

        return _Page()


@pytest.fixture
def payload() -> HHTargetedResumePayload:
    return HHTargetedResumePayload(
        profession_title="Backend Engineer",
        summary="Summary",
        education=[{"institution": "MIPT"}],
        skills=["Python", "FastAPI"],
        skill_level_hints={},
        work_experience=[{"company_name": "Acme", "position_title": "Engineer"}],
        targeted_emphasis=[],
    )


def test_constructor_run_happy_path(payload: HHTargetedResumePayload) -> None:
    client = PlaywrightTargetedResumeAutomationClient()
    fake = FakeConstructor(["profession", "main_info", "education", "skills", "experience", "final", "success"])

    result = client._run_constructor(constructor=fake, payload=payload)

    assert result.external_id == "abc123"
    assert result.resume_url == "https://hh.ru/resume/abc123"
    assert "profession:Backend Engineer" in fake.calls


def test_constructor_run_unknown_required_step_fails(payload: HHTargetedResumePayload) -> None:
    client = PlaywrightTargetedResumeAutomationClient()
    fake = FakeConstructor(["unknown"])

    with pytest.raises(HHResumeAutomationError) as exc:
        client._run_constructor(constructor=fake, payload=payload)

    assert exc.value.code == "constructor_layout_unknown"


def test_constructor_run_phone_confirmation_failure(payload: HHTargetedResumePayload) -> None:
    client = PlaywrightTargetedResumeAutomationClient()
    fake = FakeConstructor(["profession", "phone_confirmation"])

    with pytest.raises(HHResumeAutomationError) as exc:
        client._run_constructor(constructor=fake, payload=payload)

    assert exc.value.code == "phone_confirmation_required"
