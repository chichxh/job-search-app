from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import models


def test_start_hh_oauth_requires_auth(client) -> None:
    response = client.post("/api/v1/integrations/hh/connect/start")
    assert response.status_code == 401


def test_hh_status_is_scoped_to_current_user(client, auth_headers, fake_db, monkeypatch) -> None:
    monkeypatch.setenv("HH_OAUTH_CLIENT_ID", "client")
    monkeypatch.setenv("HH_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("HH_OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/hh/callback")

    fake_db.add(
        models.HHOAuthConnection(
            user_id=1,
            provider="hh",
            access_token="access-token-1",
            refresh_token="refresh-1",
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )

    response = client.get("/api/v1/integrations/hh/status", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is True
    assert "access_token" not in payload
    assert "refresh_token" not in payload


def test_hh_status_not_leaking_foreign_connection(client, foreign_auth_headers, fake_db, monkeypatch) -> None:
    monkeypatch.setenv("HH_OAUTH_CLIENT_ID", "client")
    monkeypatch.setenv("HH_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("HH_OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/hh/callback")

    fake_db.add(
        models.HHOAuthConnection(
            user_id=1,
            provider="hh",
            access_token="access-token-1",
        )
    )

    response = client.get("/api/v1/integrations/hh/status", headers=foreign_auth_headers)

    assert response.status_code == 200
    assert response.json()["connected"] is False


def test_import_hh_requires_explicit_consent(client, auth_headers, monkeypatch) -> None:
    monkeypatch.setenv("HH_OAUTH_CLIENT_ID", "client")
    monkeypatch.setenv("HH_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("HH_OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/hh/callback")

    response = client.post(
        "/api/v1/integrations/hh/import",
        headers=auth_headers,
        json={"consent": False},
    )

    assert response.status_code == 400
    assert "consent" in response.json()["detail"].lower()


def test_hh_callback_uses_safe_redirect_on_oauth_failure(client, monkeypatch) -> None:
    monkeypatch.setenv("HH_OAUTH_CLIENT_ID", "client")
    monkeypatch.setenv("HH_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("HH_OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/hh/callback")
    monkeypatch.setenv("HH_OAUTH_FRONTEND_ERROR_URL", "http://localhost:5173/settings?hh=connect_failed")

    response = client.get(
        "/api/v1/integrations/hh/callback?code=bad&state=bad",
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers.get("location", "")
    assert "connect_failed" in location


def test_hh_demo_connect_returns_403_when_demo_mode_disabled(client, auth_headers, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("HH_DEMO_MODE", raising=False)

    response = client.post("/api/v1/integrations/hh/demo-connect", headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Demo HH connection is disabled"


def test_hh_demo_connect_returns_connected_in_demo_mode(client, auth_headers, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")

    response = client.post("/api/v1/integrations/hh/demo-connect", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "connected"
    assert payload["mode"] == "demo"
    assert payload["profile"]["full_name"] == "пользователь Тестовый"
    assert payload["profile"]["title"] == "Junior Python Developer"
    assert payload["profile"]["city"] == "Москва"
    assert payload["profile"]["skills_count"] == 7
    assert payload["profile"]["experiences_count"] == 2


def test_hh_demo_connect_updates_profile_with_demo_data(client, auth_headers, fake_db, monkeypatch) -> None:
    monkeypatch.setenv("HH_DEMO_MODE", "true")

    response = client.post("/api/v1/integrations/hh/demo-connect", headers=auth_headers)
    assert response.status_code == 200

    profile = fake_db.get(models.Profile, 1)
    assert profile is not None
    assert profile.title == "Junior Python Developer"
    assert profile.city == "Москва"
    assert profile.full_name == "пользователь Тестовый"
    assert profile.skills_text == "Python, FastAPI, PostgreSQL, Docker, REST API, Git, SQL"
