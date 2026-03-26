from app.db import models


def test_register_creates_user_and_profile(client, fake_db):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new.user@example.com", "password": "strongpass123"},
    )
    assert response.status_code == 201
    assert response.json()["token_type"] == "bearer"

    users = fake_db.query(models.User).all()
    created_user = next((item for item in users if item.email == "new.user@example.com"), None)
    assert created_user is not None

    profiles = fake_db.query(models.Profile).all()
    assert any(item.user_id == created_user.id for item in profiles)


def test_login_success_and_failure(client):
    success = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@example.local", "password": "demo-password-change-me"},
    )
    assert success.status_code == 200
    assert success.json()["access_token"]

    failure = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@example.local", "password": "wrong-password"},
    )
    assert failure.status_code == 401


def test_auth_me_requires_token(client):
    unauthorized = client.get("/api/v1/auth/me")
    assert unauthorized.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@example.local", "password": "demo-password-change-me"},
    )
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    payload = me.json()
    assert payload["user"]["email"] == "demo@example.local"
    assert payload["profile_id"] == 1
