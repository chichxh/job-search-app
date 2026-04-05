from __future__ import annotations

from app.api.routers.hh_browser_integration import get_hh_connect_service
from app.db import models
from app.main import app
from app.services.hh_browser_connect_service import HHBrowserConnectService, InMemoryRuntimeRegistry, LocalSessionStorage


class FakeAdapter:
    def __init__(self, steps: list[str]) -> None:
        self.steps = steps

    def open_login_page(self) -> str:
        return self.steps.pop(0)

    def submit_identifier(self, *, identifier: str, identifier_type: str) -> str:
        return self.steps.pop(0)

    def submit_password(self, *, password: str) -> str:
        return self.steps.pop(0)

    def submit_code(self, *, code: str) -> str:
        return self.steps.pop(0)

    def export_storage_state(self) -> dict:
        return {"cookies": []}

    def close(self) -> None:
        return None

    def safe_debug_summary(self) -> dict:
        return {"url": "https://hh.ru/account/login", "title": "HH Login"}


class FakeFactory:
    def __init__(self) -> None:
        self.adapters: list[FakeAdapter] = []

    def push(self, adapter: FakeAdapter) -> None:
        self.adapters.append(adapter)

    def create(self) -> FakeAdapter:
        return self.adapters.pop(0)


class MemoryStorage(LocalSessionStorage):
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def save(self, *, user_id: int, connection_id: int, state: dict) -> str:
        self.saved.append({"user_id": user_id, "connection_id": connection_id, "state": state})
        return f"local://hh-browser-session/{user_id}-{connection_id}"


def _override_service(fake_db, factory: FakeFactory, storage: MemoryStorage):
    runtime_registry = InMemoryRuntimeRegistry(timeout_seconds=120)

    def _factory_override():
        return HHBrowserConnectService(
            fake_db,
            adapter_factory=factory,
            runtime_registry=runtime_registry,
            session_storage=storage,
        )

    return _factory_override


def test_connect_flow_state_machine_api(client, auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    factory.push(FakeAdapter(["awaiting_identifier", "awaiting_password", "awaiting_code", "connected"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage)

    start = client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    assert start.status_code == 200
    assert start.json()["status"] == "awaiting_identifier"

    identifier = client.post(
        "/api/v1/integrations/hh-browser/connect/identifier",
        headers=auth_headers,
        json={"identifier_type": "email", "identifier": "user@example.com"},
    )
    assert identifier.status_code == 200
    assert identifier.json()["status"] == "awaiting_password"

    password = client.post(
        "/api/v1/integrations/hh-browser/connect/password",
        headers=auth_headers,
        json={"password": "secret"},
    )
    assert password.status_code == 200
    assert password.json()["status"] == "awaiting_code"

    code = client.post(
        "/api/v1/integrations/hh-browser/connect/code",
        headers=auth_headers,
        json={"code": "1234"},
    )
    assert code.status_code == 200
    assert code.json()["status"] == "connected"

    assert storage.saved


def test_invalid_transition_returns_400(client, auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    factory.push(FakeAdapter(["awaiting_identifier"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage)

    client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    invalid = client.post("/api/v1/integrations/hh-browser/connect/code", headers=auth_headers, json={"code": "0000"})

    assert invalid.status_code == 400


def test_foreign_user_access_isolated(client, auth_headers, foreign_auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    factory.push(FakeAdapter(["awaiting_identifier"]))
    factory.push(FakeAdapter(["awaiting_identifier"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage)

    owner_start = client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    assert owner_start.status_code == 200

    foreign_state = client.get("/api/v1/integrations/hh-browser/connect/state", headers=foreign_auth_headers)
    assert foreign_state.status_code == 200
    assert foreign_state.json()["status"] == "disconnected"


def test_cancel_moves_to_disconnected(client, auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    factory.push(FakeAdapter(["awaiting_identifier"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage)

    client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    cancel = client.post("/api/v1/integrations/hh-browser/connect/cancel", headers=auth_headers)

    assert cancel.status_code == 200
    assert cancel.json()["status"] == "disconnected"


def test_secrets_not_persisted_in_db(client, auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    factory.push(FakeAdapter(["awaiting_identifier", "awaiting_password", "awaiting_code", "connected"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage)

    client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    client.post(
        "/api/v1/integrations/hh-browser/connect/identifier",
        headers=auth_headers,
        json={"identifier_type": "email", "identifier": "private@example.com"},
    )
    client.post("/api/v1/integrations/hh-browser/connect/password", headers=auth_headers, json={"password": "top-secret"})
    client.post("/api/v1/integrations/hh-browser/connect/code", headers=auth_headers, json={"code": "999999"})

    stored = next((item for item in fake_db.query(models.HHBrowserConnection).all() if item.user_id == 1), None)
    assert stored is not None
    serialized = str(vars(stored))
    assert "top-secret" not in serialized
    assert "999999" not in serialized
    assert "private@example.com" not in serialized
    assert stored.session_state_ref is not None

    state = client.get("/api/v1/integrations/hh-browser/connect/state", headers=auth_headers)
    assert state.status_code == 200
    body = str(state.json())
    assert "top-secret" not in body
    assert "999999" not in body
    assert "private@example.com" not in body
