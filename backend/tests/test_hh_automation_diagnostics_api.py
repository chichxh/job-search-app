from __future__ import annotations

from app.db import models


def test_hh_diagnostics_summary_includes_safe_operational_view(client, auth_headers, fake_db) -> None:
    fake_db.add(
        models.HHBrowserConnection(
            user_id=1,
            status="requires_reauth",
            requires_reauth=True,
            session_state_ref="local://hh-browser-session/session_123.json",
            last_error_code="session_expired",
            last_error_message="Persisted HH browser session reached cookie expiry",
        )
    )
    fake_db.add(
        models.HHManagedResume(
            user_id=1,
            profile_id=1,
            status="failed",
            visibility_status="change_failed",
            visibility_error_code="selector_not_found",
            visibility_error_message="controls missing",
            hh_resume_external_id="hh-resume-1",
        )
    )
    fake_db.add(
        models.HHAutomationActionRun(
            user_id=1,
            action_type="apply",
            target_type="managed_resume_vacancy",
            target_id=10,
            request_fingerprint="fp-1",
            status="retryable_failed",
            operation_code="HH_APPLY_RETRYABLE_FAILED",
            safe_summary="HH apply failed with code=apply_surface_not_available",
        )
    )
    fake_db.add(
        models.HHAutomationActionRun(
            user_id=1,
            action_type="connect",
            target_type="browser_connection",
            target_id=1,
            request_fingerprint="fp-2",
            status="failed",
            operation_code="HH_CONNECT_FAILED",
            safe_summary="HH connect flow failed with code=session_expired",
        )
    )

    response = client.get("/api/v1/integrations/hh-browser/diagnostics", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["connection"]["status"] == "requires_reauth"
    assert payload["connection"]["requires_reauth"] is True
    assert payload["managed_resumes"]["failed"] == 1
    assert payload["managed_resumes"]["visibility_change_failed"] == 1
    assert payload["recent_failures"]
    assert payload["recent_failures"][0]["diagnostic_reason"] in {
        "apply_surface_unavailable",
        "session_expired",
    }
    assert "session_123" not in str(payload)


def test_hh_diagnostics_actions_endpoint_is_safe_and_scoped(client, auth_headers, foreign_auth_headers, fake_db) -> None:
    fake_db.add(
        models.HHAutomationActionRun(
            user_id=1,
            action_type="create_targeted_resume",
            target_type="profile",
            target_id=1,
            request_fingerprint="fp-owner",
            status="failed",
            operation_code="HH_TARGETED_RESUME_RETRYABLE_FAILED",
            safe_summary="Targeted resume creation failed with code=resume_surface_not_available",
        )
    )
    fake_db.add(
        models.HHAutomationActionRun(
            user_id=2,
            action_type="apply",
            target_type="managed_resume_vacancy",
            target_id=99,
            request_fingerprint="fp-foreign",
            status="failed",
            operation_code="HH_APPLY_TERMINAL_FAILED",
            safe_summary="HH apply failed with code=RESUME_SELECTION_MISMATCH",
        )
    )

    response = client.get("/api/v1/integrations/hh-browser/diagnostics/actions?limit=5", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["action_type"] == "create_targeted_resume"
    assert payload[0]["diagnostic_reason"] == "resume_constructor_surface_unavailable"
    assert "request_fingerprint" not in payload[0]
    assert "context_ref" not in payload[0]

    foreign_response = client.get("/api/v1/integrations/hh-browser/diagnostics/actions?limit=5", headers=foreign_auth_headers)
    assert foreign_response.status_code == 200
    assert foreign_response.json()[0]["target_id"] == 99
