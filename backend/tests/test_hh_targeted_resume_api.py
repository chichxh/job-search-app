from __future__ import annotations

from datetime import date

from app.api.routers.hh_browser_integration import get_hh_targeted_resume_service
from app.db import models
from app.main import app
from app.schemas.hh_browser_integration import HHCreateTargetedResumeRequest
from app.services.hh_targeted_resume_service import (
    HHCreateResumeResult,
    HHCreateTargetedResumeService,
    HHResumeAutomationClient,
    HHResumeAutomationError,
    HHTargetedPayloadBuilder,
)


class FakeAutomationClient(HHResumeAutomationClient):
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def create_targeted_resume(self, *, user_id, connection, payload, dry_run):
        if self.should_fail:
            raise HHResumeAutomationError(
                code="internal_automation_error",
                message="secret-token-123 is invalid and should be redacted",
            )
        return HHCreateResumeResult(
            external_id=f"hh-{user_id}-resume-1",
            resume_url="https://hh.ru/resume/abc123",
            title=payload.profession_title,
        )


def _override_service(fake_db, *, should_fail: bool = False):
    def _factory_override():
        return HHCreateTargetedResumeService(
            fake_db,
            payload_builder=HHTargetedPayloadBuilder(fake_db),
            automation_client=FakeAutomationClient(should_fail=should_fail),
        )

    return _factory_override


def _seed_profile_details(fake_db, *, profile_id: int) -> None:
    fake_db.add(
        models.ProfileSkill(
            profile_id=profile_id,
            name_raw="Python",
            normalized_key="python",
            category="language",
            level="advanced",
            years=7,
            is_primary=True,
        )
    )
    fake_db.add(
        models.ProfileSkill(
            profile_id=profile_id,
            name_raw="FastAPI",
            normalized_key="fastapi",
            category="framework",
            level="middle",
            years=3,
            is_primary=True,
        )
    )
    fake_db.add(
        models.ProfileEducation(
            profile_id=profile_id,
            institution="MIPT",
            degree_level="bachelor",
            field_of_study="Computer Science",
            start_year=2014,
            end_year=2018,
        )
    )
    fake_db.add(
        models.ProfileExperience(
            profile_id=profile_id,
            company_name="Acme",
            position_title="Backend Engineer",
            start_date=date(2020, 1, 1),
            end_date=None,
            is_current=True,
            responsibilities_text="Built APIs",
            achievements_text="Improved latency",
            tech_stack_text="Python, FastAPI, PostgreSQL",
        )
    )


def test_payload_builder_composes_targeted_draft(fake_db) -> None:
    profile = fake_db.get(models.Profile, 1)
    assert profile is not None
    _seed_profile_details(fake_db, profile_id=profile.id)

    builder = HHTargetedPayloadBuilder(fake_db)
    payload = builder.build(
        profile=profile,
        vacancy=fake_db.get(models.Vacancy, 1),
        source_resume_version=None,
        request=HHCreateTargetedResumeRequest(
            profile_id=1,
            vacancy_id=1,
            skills_focus=["FastAPI"],
            include_skill_levels=True,
            dry_run=True,
        ),
    )

    assert payload.profession_title == "Senior Backend Engineer"
    assert "FastAPI" in payload.skills
    assert payload.education
    assert payload.work_experience
    assert payload.skill_level_hints.get("FastAPI") == "middle"


def test_create_targeted_requires_active_connection(client, auth_headers, fake_db) -> None:
    app.dependency_overrides[get_hh_targeted_resume_service] = _override_service(fake_db)
    response = client.post(
        "/api/v1/integrations/hh-browser/resumes/create-targeted",
        headers=auth_headers,
        json={"profile_id": 1, "vacancy_id": 1},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Active HH browser session required"


def test_create_targeted_creates_record_and_created_status(client, auth_headers, fake_db) -> None:
    _seed_profile_details(fake_db, profile_id=1)
    fake_db.add(
        models.HHBrowserConnection(
            user_id=1,
            status="connected",
            requires_reauth=False,
            session_state_ref="local://hh-browser-session/u1.json",
        )
    )
    app.dependency_overrides[get_hh_targeted_resume_service] = _override_service(fake_db)

    response = client.post(
        "/api/v1/integrations/hh-browser/resumes/create-targeted",
        headers=auth_headers,
        json={"profile_id": 1, "vacancy_id": 1},
    )
    assert response.status_code == 201
    body = response.json()["managed_resume"]
    assert body["status"] == "created"
    assert body["hh_resume_external_id"] == "hh-1-resume-1"
    assert body["hh_resume_url"] == "https://hh.ru/resume/abc123"
    assert body["title"] == "Senior Backend Engineer"
    assert body["auto_hide_from_all_enabled"] is True
    assert body["intended_hidden_from_all"] is True
    assert body["user_opted_out_of_auto_hide_from_all"] is False


def test_foreign_access_to_managed_resume_denied(client, auth_headers, foreign_auth_headers, fake_db) -> None:
    fake_db.add(
        models.HHManagedResume(
            user_id=1,
            profile_id=1,
            vacancy_id=1,
            title="Backend Engineer",
            status="created",
            hh_resume_external_id="hh-owner-1",
        )
    )

    response = client.get("/api/v1/integrations/hh-browser/resumes/1", headers=foreign_auth_headers)
    assert response.status_code == 404


def test_failed_automation_persists_safe_error(client, auth_headers, fake_db) -> None:
    _seed_profile_details(fake_db, profile_id=1)
    fake_db.add(
        models.HHBrowserConnection(
            user_id=1,
            status="connected",
            requires_reauth=False,
            session_state_ref="local://hh-browser-session/u1.json",
        )
    )
    app.dependency_overrides[get_hh_targeted_resume_service] = _override_service(fake_db, should_fail=True)

    response = client.post(
        "/api/v1/integrations/hh-browser/resumes/create-targeted",
        headers=auth_headers,
        json={"profile_id": 1, "vacancy_id": 1},
    )

    assert response.status_code == 201
    managed = response.json()["managed_resume"]
    assert managed["status"] == "failed"
    assert managed["last_error_code"] == "internal_automation_error"
    assert "secret-token-123" not in (managed["last_error_message"] or "")


def test_create_targeted_duplicate_request_is_idempotent(client, auth_headers, fake_db) -> None:
    _seed_profile_details(fake_db, profile_id=1)
    fake_db.add(
        models.HHBrowserConnection(
            user_id=1,
            status="connected",
            requires_reauth=False,
            session_state_ref="local://hh-browser-session/u1.json",
        )
    )
    app.dependency_overrides[get_hh_targeted_resume_service] = _override_service(fake_db)

    first = client.post(
        "/api/v1/integrations/hh-browser/resumes/create-targeted",
        headers=auth_headers,
        json={"profile_id": 1, "vacancy_id": 1},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/integrations/hh-browser/resumes/create-targeted",
        headers=auth_headers,
        json={"profile_id": 1, "vacancy_id": 1},
    )
    assert second.status_code == 201
    assert second.json()["managed_resume"]["id"] == first.json()["managed_resume"]["id"]

    action_runs = fake_db.query(models.HHAutomationActionRun).all()
    assert any(item.action_type == "create_targeted_resume" and item.status == "completed" for item in action_runs)
    assert any(
        item.action_type == "create_targeted_resume" and item.status == "duplicate_prevented" for item in action_runs
    )


def test_create_targeted_explicit_opt_out_disables_auto_hide(client, auth_headers, fake_db) -> None:
    _seed_profile_details(fake_db, profile_id=1)
    fake_db.add(
        models.HHBrowserConnection(
            user_id=1,
            status="connected",
            requires_reauth=False,
            session_state_ref="local://hh-browser-session/u1.json",
        )
    )
    app.dependency_overrides[get_hh_targeted_resume_service] = _override_service(fake_db)

    response = client.post(
        "/api/v1/integrations/hh-browser/resumes/create-targeted",
        headers=auth_headers,
        json={"profile_id": 1, "vacancy_id": 1, "do_not_hide_from_all_employers": True},
    )
    assert response.status_code == 201
    body = response.json()["managed_resume"]
    assert body["auto_hide_from_all_enabled"] is False
    assert body["intended_hidden_from_all"] is False
    assert body["user_opted_out_of_auto_hide_from_all"] is True
    assert body["desired_visibility_mode"] == "public_default"
