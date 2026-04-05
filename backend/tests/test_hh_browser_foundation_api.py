from __future__ import annotations

from app.db import models


def test_hh_browser_connect_init_creates_or_updates_connection(client, auth_headers, fake_db) -> None:
    first = client.post("/api/v1/integrations/hh-browser/connect/init", headers=auth_headers, json={})
    assert first.status_code == 200
    assert first.json()["status"] == "connecting"

    stored = next((item for item in fake_db.query(models.HHBrowserConnection).all() if item.user_id == 1), None)
    assert stored is not None

    second = client.post(
        "/api/v1/integrations/hh-browser/connect/init",
        headers=auth_headers,
        json={"session_state_ref": "slot://user/1/session"},
    )
    assert second.status_code == 200
    assert second.json()["session_present"] is True

    all_for_user = [item for item in fake_db.query(models.HHBrowserConnection).all() if item.user_id == 1]
    assert len(all_for_user) == 1


def test_hh_browser_status_returns_only_current_user_connection(client, auth_headers, foreign_auth_headers, fake_db) -> None:
    fake_db.add(models.HHBrowserConnection(user_id=1, status="connected", session_state_ref="slot://1"))
    fake_db.add(models.HHBrowserConnection(user_id=2, status="failed", last_error_message="foreign"))

    response = client.get("/api/v1/integrations/hh-browser/status", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "connected"
    assert payload["session_present"] is True
    assert payload["last_error_message"] is None

    foreign = client.get("/api/v1/integrations/hh-browser/status", headers=foreign_auth_headers)
    assert foreign.status_code == 200
    assert foreign.json()["status"] == "failed"


def test_hh_browser_status_transitions_for_current_user(client, auth_headers) -> None:
    init_res = client.post("/api/v1/integrations/hh-browser/connect/init", headers=auth_headers, json={})
    assert init_res.status_code == 200
    assert init_res.json()["status"] == "connecting"

    awaiting = client.post(
        "/api/v1/integrations/hh-browser/mark-awaiting-code",
        headers=auth_headers,
        json={"requires_reauth": True},
    )
    assert awaiting.status_code == 200
    assert awaiting.json()["status"] == "awaiting_code"
    assert awaiting.json()["requires_reauth"] is True

    connected = client.post(
        "/api/v1/integrations/hh-browser/mark-connected",
        headers=auth_headers,
        json={"session_state_ref": "slot://session/ok"},
    )
    assert connected.status_code == 200
    assert connected.json()["status"] == "connected"
    assert connected.json()["session_present"] is True
    assert connected.json()["last_authenticated_at"] is not None

    failed = client.post(
        "/api/v1/integrations/hh-browser/mark-failed",
        headers=auth_headers,
        json={"error_code": "NETWORK", "error_message": "Temporary timeout", "requires_reauth": False},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["last_error_code"] == "NETWORK"


def test_hh_browser_requires_auth_and_denies_foreign_changes(client, foreign_auth_headers, fake_db) -> None:
    unauthorized = client.post("/api/v1/integrations/hh-browser/mark-failed", json={"error_message": "x"})
    assert unauthorized.status_code == 401

    fake_db.add(models.HHBrowserConnection(user_id=1, status="connected", session_state_ref="slot://owner"))

    foreign_disconnect = client.post("/api/v1/integrations/hh-browser/disconnect", headers=foreign_auth_headers)
    assert foreign_disconnect.status_code == 200

    owner = next((item for item in fake_db.query(models.HHBrowserConnection).all() if item.user_id == 1), None)
    foreign = next((item for item in fake_db.query(models.HHBrowserConnection).all() if item.user_id == 2), None)
    assert owner is not None and owner.status == "connected"
    assert foreign is not None and foreign.status == "disconnected"


def test_hh_browser_disconnect_clears_session_reference(client, auth_headers, fake_db) -> None:
    fake_db.add(
        models.HHBrowserConnection(
            user_id=1,
            status="connected",
            session_state_ref="slot://session",
            session_expires_at=None,
        )
    )

    response = client.post("/api/v1/integrations/hh-browser/disconnect", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "disconnected"
    assert payload["session_present"] is False

    stored = next((item for item in fake_db.query(models.HHBrowserConnection).all() if item.user_id == 1), None)
    assert stored is not None
    assert stored.session_state_ref is None


def test_hh_browser_failed_state_stores_short_safe_error_summary(client, auth_headers) -> None:
    long_error = "Failed with token=secret-token and email test@example.com " + ("x" * 220)
    response = client.post(
        "/api/v1/integrations/hh-browser/mark-failed",
        headers=auth_headers,
        json={"error_code": "AUTH", "error_message": long_error, "requires_reauth": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["requires_reauth"] is True
    assert payload["last_error_code"] == "AUTH"
    assert payload["last_error_message"] is not None
    assert "test@example.com" not in payload["last_error_message"]
    assert len(payload["last_error_message"]) <= 163
