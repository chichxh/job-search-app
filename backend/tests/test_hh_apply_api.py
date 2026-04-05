from __future__ import annotations

from app.api.routers.hh_browser_integration import get_hh_apply_service
from app.db import models
from app.main import app
from app.services.hh_apply_service import (
    HHApplyAutomationClient,
    HHApplyAutomationError,
    HHApplyAutomationResult,
    HHApplyService,
)
from app.services.hh_resume_visibility_service import HHResumeVisibilityService


class FakeApplyAutomationClient(HHApplyAutomationClient):
    def __init__(self, *, should_fail: bool = False, retryable: bool = True, result_type: str = "submitted") -> None:
        self.should_fail = should_fail
        self.retryable = retryable
        self.result_type = result_type

    def apply_to_vacancy(self, *, user_id, connection, apply_run, managed_resume, vacancy, cover_letter_text, dry_run):
        if self.should_fail:
            raise HHApplyAutomationError(
                code="transient_wait",
                message="temporary issue",
                retryable=self.retryable,
                response_ref={"hh_response_type": "captcha"},
            )
        return HHApplyAutomationResult(
            result_type="dry_run" if dry_run else self.result_type,
            result_message="Apply simulated" if dry_run else "Apply submitted",
            response_ref={"hh_response_type": "ok", "hh_apply_id": f"hh-apply-{apply_run.id}"},
        )


class FakeVisibilityService(HHResumeVisibilityService):
    def __init__(self, db, *, fail_to_hide: bool = False) -> None:
        self.db = db
        self.fail_to_hide = fail_to_hide

    def hide_from_all(self, *, user_id: int, managed_resume_id: int):
        managed = self.db.get(models.HHManagedResume, managed_resume_id)
        assert managed is not None
        if self.fail_to_hide:
            managed.current_visibility_mode = "public_default"
            return managed
        managed.current_visibility_mode = "hidden_from_all"
        managed.visibility_status = "updated"
        return managed


def _override_service(
    fake_db,
    *,
    should_fail: bool = False,
    retryable: bool = True,
    result_type: str = "submitted",
    visibility_service: HHResumeVisibilityService | None = None,
):
    def _factory_override():
        return HHApplyService(
            fake_db,
            automation_client=FakeApplyAutomationClient(
                should_fail=should_fail,
                retryable=retryable,
                result_type=result_type,
            ),
            visibility_service=visibility_service,
        )

    return _factory_override


def _seed_connected_session(fake_db) -> None:
    fake_db.add(
        models.HHBrowserConnection(
            user_id=1,
            status="connected",
            requires_reauth=False,
            session_state_ref="local://hh-browser-session/u1.json",
        )
    )


def _seed_managed_resume(fake_db, *, user_id: int = 1, profile_id: int = 1, external_id: str | None = "hh-resume-1") -> models.HHManagedResume:
    item = models.HHManagedResume(
        user_id=user_id,
        profile_id=profile_id,
        vacancy_id=1,
        hh_resume_external_id=external_id,
        hh_resume_url="https://hh.ru/resume/1",
        title="Backend Engineer",
        status="created",
        auto_hide_from_all_enabled=True,
        desired_visibility_mode="hidden_from_all",
        current_visibility_mode="hidden_from_all",
    )
    fake_db.add(item)
    return item


def test_apply_requires_active_session(client, auth_headers, fake_db) -> None:
    managed = _seed_managed_resume(fake_db)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db)

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "HH_SESSION_REQUIRED"


def test_apply_ownership_and_foreign_access_denied(client, auth_headers, foreign_auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    owner_managed = _seed_managed_resume(fake_db)
    foreign_profile = next(item for item in fake_db.query(models.Profile).all() if item.user_id == 2)
    foreign_managed = _seed_managed_resume(fake_db, user_id=2, profile_id=foreign_profile.id)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db)

    ok = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": owner_managed.id},
    )
    assert ok.status_code == 201

    forbidden = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": foreign_managed.id},
    )
    assert forbidden.status_code == 404

    list_foreign = client.get("/api/v1/integrations/hh-browser/apply-runs", headers=foreign_auth_headers)
    assert list_foreign.status_code == 200
    assert list_foreign.json() == []


def test_apply_creates_lifecycle_statuses_and_dry_run(client, auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db)

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id, "dry_run": True},
    )

    assert response.status_code == 201
    body = response.json()["hh_apply_run"]
    assert body["status"] == "submitted"
    assert body["result_type"] == "dry_run"
    managed = fake_db.get(models.HHManagedResume, managed.id)
    assert managed is not None
    assert managed.current_visibility_mode == "visible_selected_employers"
    assert managed.visibility_status == "inferred_post_apply"

    runs = client.get("/api/v1/integrations/hh-browser/apply-runs", headers=auth_headers)
    assert runs.status_code == 200
    assert len(runs.json()) == 1


def test_apply_failure_persists_normalized_error(client, auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db, should_fail=True, retryable=True)

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id},
    )
    assert response.status_code == 201
    body = response.json()["hh_apply_run"]
    assert body["status"] == "retryable_failed"
    assert body["result_type"] == "transient_wait"
    assert "temporary issue" not in (body["result_message"] or "")


def test_apply_cover_letter_ownership_validation(client, auth_headers, foreign_auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db)

    foreign_profile = next(item for item in fake_db.query(models.Profile).all() if item.user_id == 2)
    foreign_cover = models.CoverLetterVersion(profile_id=foreign_profile.id, content_text="foreign", status="approved")
    fake_db.add(foreign_cover)

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={
            "vacancy_id": 1,
            "hh_resume_managed_id": managed.id,
            "cover_letter_version_id": foreign_cover.id,
        },
    )
    assert response.status_code == 404

    owner_run = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={
            "vacancy_id": 1,
            "hh_resume_managed_id": managed.id,
            "cover_letter_text": "  Custom message for this vacancy  ",
            "dry_run": True,
        },
    )
    assert owner_run.status_code == 201

    no_access = client.get("/api/v1/integrations/hh-browser/apply-runs/1", headers=foreign_auth_headers)
    assert no_access.status_code == 404


def test_apply_rejects_missing_hh_resume_external_reference(client, auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db, external_id=None)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db)

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "HH_RESUME_EXTERNAL_REF_MISSING"


def test_apply_flow_enforces_hidden_from_all_when_policy_enabled(client, auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db)
    managed.current_visibility_mode = "public_default"
    visibility_service = FakeVisibilityService(fake_db)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db, visibility_service=visibility_service)

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id},
    )
    assert response.status_code == 201
    updated = fake_db.get(models.HHManagedResume, managed.id)
    assert updated is not None
    assert updated.current_visibility_mode == "visible_selected_employers"
    assert updated.visibility_status == "inferred_post_apply"


def test_apply_opt_out_path_does_not_force_visibility_change(client, auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db)
    managed.auto_hide_from_all_enabled = False
    managed.desired_visibility_mode = "public_default"
    managed.current_visibility_mode = "public_default"
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db)

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id},
    )
    assert response.status_code == 201
    updated = fake_db.get(models.HHManagedResume, managed.id)
    assert updated is not None
    assert updated.current_visibility_mode == "public_default"
    assert updated.visibility_status != "inferred_post_apply"
