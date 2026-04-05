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


class FakeApplyAutomationClient(HHApplyAutomationClient):
    def __init__(self, *, should_fail: bool = False, retryable: bool = True, result_type: str = "submitted") -> None:
        self.should_fail = should_fail
        self.retryable = retryable
        self.result_type = result_type

    def apply_to_vacancy(self, *, user_id, connection, apply_run, managed_resume, vacancy, cover_letter_text, dry_run):
        if self.should_fail:
            raise HHApplyAutomationError(
                code="TRANSIENT_WAIT",
                message="temporary issue",
                retryable=self.retryable,
                response_ref={"hh_response_type": "captcha"},
            )
        return HHApplyAutomationResult(
            result_type="dry_run" if dry_run else self.result_type,
            result_message="Apply simulated" if dry_run else "Apply submitted",
            response_ref={"hh_response_type": "ok", "hh_apply_id": f"hh-apply-{apply_run.id}"},
        )


def _override_service(fake_db, *, should_fail: bool = False, retryable: bool = True, result_type: str = "submitted"):
    def _factory_override():
        return HHApplyService(
            fake_db,
            automation_client=FakeApplyAutomationClient(
                should_fail=should_fail,
                retryable=retryable,
                result_type=result_type,
            ),
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


def _seed_managed_resume(fake_db, *, user_id: int = 1, profile_id: int = 1) -> models.HHManagedResume:
    item = models.HHManagedResume(
        user_id=user_id,
        profile_id=profile_id,
        vacancy_id=1,
        hh_resume_external_id="hh-resume-1",
        hh_resume_url="https://hh.ru/resume/1",
        title="Backend Engineer",
        status="created",
        current_visibility_mode="unknown",
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
    body = response.json()
    assert body["status"] == "submitted"
    assert body["result_type"] == "dry_run"

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
    body = response.json()
    assert body["status"] == "retryable_failed"
    assert body["result_type"] == "TRANSIENT_WAIT"
    assert "temporary issue" not in (body["result_message"] or "")
    assert fake_db.query(models.Application).all() == []


def test_apply_submitted_syncs_into_applications_funnel(client, auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db, result_type="submitted")

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id},
    )
    assert response.status_code == 201

    applications = fake_db.query(models.Application).all()
    assert len(applications) == 1
    created = applications[0]
    assert created.status == "applied"
    assert created.last_hh_apply_run_id == 1
    assert created.hh_managed_resume_id == managed.id
    assert created.external_apply_status == "submitted"

    history = fake_db.query(models.ApplicationStatusHistory).all()
    assert len(history) == 1
    assert history[0].application_id == created.id
    assert history[0].to_status == "applied"
    assert history[0].hh_apply_run_id == 1


def test_apply_submitted_updates_existing_application_without_duplicates(client, auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db)
    existing = models.Application(profile_id=1, vacancy_id=1, status="planned")
    fake_db.add(existing)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db, result_type="submitted")

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id},
    )
    assert response.status_code == 201

    applications = fake_db.query(models.Application).all()
    assert len(applications) == 1
    updated = applications[0]
    assert updated.id == existing.id
    assert updated.status == "applied"
    assert updated.last_hh_apply_run_id == 1

    history = fake_db.query(models.ApplicationStatusHistory).all()
    assert len(history) == 1
    assert history[0].from_status == "planned"
    assert history[0].to_status == "applied"


def test_apply_already_applied_syncs_predictably_and_is_idempotent(client, auth_headers, fake_db) -> None:
    _seed_connected_session(fake_db)
    managed = _seed_managed_resume(fake_db)
    app.dependency_overrides[get_hh_apply_service] = _override_service(fake_db, result_type="already_applied")

    response = client.post(
        "/api/v1/integrations/hh-browser/apply",
        headers=auth_headers,
        json={"vacancy_id": 1, "hh_resume_managed_id": managed.id},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "already_applied"

    manual_sync = client.post(
        "/api/v1/integrations/hh-browser/apply-runs/1/sync-to-application",
        headers=auth_headers,
    )
    assert manual_sync.status_code == 200
    assert manual_sync.json()["synced"] is True

    applications = fake_db.query(models.Application).all()
    assert len(applications) == 1
    assert applications[0].status == "applied"
    assert applications[0].external_apply_status == "already_applied"

    history = fake_db.query(models.ApplicationStatusHistory).all()
    assert len(history) == 1
    assert history[0].hh_apply_run_id == 1


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
