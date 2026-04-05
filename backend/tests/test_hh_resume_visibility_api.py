from __future__ import annotations

from datetime import datetime, timezone

from app.api.routers.hh_browser_integration import get_hh_resume_visibility_service
from app.db import models
from app.main import app
from app.services.hh_resume_visibility_service import (
    HHResumeVisibilityAutomationClient,
    HHResumeVisibilityAutomationError,
    HHResumeVisibilityChangeResult,
    HHResumeVisibilityResult,
    HHResumeVisibilityService,
)


class FakeVisibilityAutomation(HHResumeVisibilityAutomationClient):
    def __init__(self, *, fail_check: bool = False, fail_hide: bool = False) -> None:
        self.fail_check = fail_check
        self.fail_hide = fail_hide

    def detect_visibility(self, *, user_id, connection, managed_resume):
        if self.fail_check:
            raise HHResumeVisibilityAutomationError(
                code="VISIBILITY_CHECK_FAILED",
                message="dom dump: secret-cookie",
            )
        return HHResumeVisibilityResult(
            current_visibility_mode="public_default",
            checked_at=datetime.now(timezone.utc),
        )

    def hide_from_all(self, *, user_id, connection, managed_resume):
        if self.fail_hide:
            raise HHResumeVisibilityAutomationError(
                code="VISIBILITY_CHANGE_FAILED",
                message="raw html: super secret",
            )
        now = datetime.now(timezone.utc)
        return HHResumeVisibilityChangeResult(
            current_visibility_mode="hidden_from_all",
            checked_at=now,
            changed_at=now,
        )


def _override_service(fake_db, *, fail_check: bool = False, fail_hide: bool = False):
    def _factory_override():
        return HHResumeVisibilityService(
            fake_db,
            automation_client=FakeVisibilityAutomation(fail_check=fail_check, fail_hide=fail_hide),
        )

    return _factory_override


def _seed_managed_resume(fake_db, *, user_id: int = 1, profile_id: int = 1, external_id: str = "hh-resume-1") -> None:
    fake_db.add(
        models.HHManagedResume(
            user_id=user_id,
            profile_id=profile_id,
            title="Backend Engineer",
            status="created",
            hh_resume_external_id=external_id,
            desired_visibility_mode="hidden_from_all",
            current_visibility_mode="unknown",
            visibility_status="idle",
        )
    )


def _seed_connected_session(fake_db, *, user_id: int = 1) -> None:
    fake_db.add(
        models.HHBrowserConnection(
            user_id=user_id,
            status="connected",
            requires_reauth=False,
            session_state_ref="local://hh-browser-session/u1.json",
        )
    )


def test_visibility_check_requires_active_session(client, auth_headers, fake_db) -> None:
    _seed_managed_resume(fake_db)
    app.dependency_overrides[get_hh_resume_visibility_service] = _override_service(fake_db)

    response = client.post("/api/v1/integrations/hh-browser/resumes/1/visibility/check", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Active HH browser session required"


def test_hide_from_all_updates_local_state_on_success(client, auth_headers, fake_db) -> None:
    _seed_managed_resume(fake_db)
    _seed_connected_session(fake_db)
    app.dependency_overrides[get_hh_resume_visibility_service] = _override_service(fake_db)

    response = client.post("/api/v1/integrations/hh-browser/resumes/1/visibility/hide-from-all", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["desired_visibility_mode"] == "hidden_from_all"
    assert body["current_visibility_mode"] == "hidden_from_all"
    assert body["visibility_status"] == "updated"
    assert body["visibility_last_checked_at"] is not None
    assert body["visibility_last_changed_at"] is not None


def test_visibility_failure_persists_normalized_error(client, auth_headers, fake_db) -> None:
    _seed_managed_resume(fake_db)
    _seed_connected_session(fake_db)
    app.dependency_overrides[get_hh_resume_visibility_service] = _override_service(fake_db, fail_hide=True)

    response = client.post("/api/v1/integrations/hh-browser/resumes/1/visibility/hide-from-all", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["current_visibility_mode"] == "change_failed"
    assert body["visibility_status"] == "change_failed"
    assert body["visibility_error_code"] == "VISIBILITY_CHANGE_FAILED"
    assert "super secret" not in (body["visibility_error_message"] or "")


def test_foreign_access_denied_for_visibility(client, foreign_auth_headers, fake_db) -> None:
    _seed_managed_resume(fake_db, user_id=1, profile_id=1)
    _seed_connected_session(fake_db, user_id=2)
    app.dependency_overrides[get_hh_resume_visibility_service] = _override_service(fake_db)

    response = client.get("/api/v1/integrations/hh-browser/resumes/1/visibility", headers=foreign_auth_headers)
    assert response.status_code == 404


def test_visibility_check_updates_current_mode_predictably(client, auth_headers, fake_db) -> None:
    _seed_managed_resume(fake_db)
    _seed_connected_session(fake_db)
    app.dependency_overrides[get_hh_resume_visibility_service] = _override_service(fake_db)

    response = client.post("/api/v1/integrations/hh-browser/resumes/1/visibility/check", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["current_visibility_mode"] == "public_default"
    assert body["visibility_status"] == "updated"
    assert body["visibility_error_code"] is None
