from __future__ import annotations

from app.api.routers.hh_browser_integration import get_hh_connect_service
from app.db import models
from app.main import app
from app.services.hh_browser_connect_service import HHBrowserConnectService, InMemoryRuntimeRegistry


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


class MemoryStorage:
    def __init__(self) -> None:
        self.saved: list[dict] = []
        self.by_ref: dict[str, dict] = {}
        self.deleted: list[str] = []

    def save(self, *, user_id: int, connection_id: int, state: dict) -> str:
        ref = f"local://hh-browser-session/{user_id}-{connection_id}-{len(self.saved)+1}"
        self.saved.append({"user_id": user_id, "connection_id": connection_id, "state": state, "ref": ref})
        self.by_ref[ref] = state
        return ref

    def load(self, *, ref: str) -> dict:
        if ref not in self.by_ref:
            raise FileNotFoundError(ref)
        return self.by_ref[ref]

    def delete(self, *, ref: str) -> None:
        self.deleted.append(ref)
        self.by_ref.pop(ref, None)


class FakeProbe:
    def __init__(self, *, authenticated: bool = True) -> None:
        self.authenticated = authenticated

    def check_authenticated(self) -> bool:
        return self.authenticated

    def close(self) -> None:
        return None


class FakeProbeFactory:
    def __init__(self, responses: list[bool] | None = None) -> None:
        self.responses = responses or [True]

    def create(self, *, storage_state: dict) -> FakeProbe:
        return FakeProbe(authenticated=self.responses.pop(0))


def _override_service(fake_db, factory: FakeFactory, storage: MemoryStorage, probe_factory: FakeProbeFactory | None = None):
    runtime_registry = InMemoryRuntimeRegistry(timeout_seconds=120)

    def _factory_override():
        return HHBrowserConnectService(
            fake_db,
            adapter_factory=factory,
            runtime_registry=runtime_registry,
            session_storage=storage,
            session_probe_factory=probe_factory or FakeProbeFactory([True]),
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
    assert "session_state_ref" not in code.json()
    assert "cookies" not in str(code.json()).lower()
    assert "storage_state" not in str(code.json()).lower()

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
    factory.push(FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage)

    client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    client.post(
        "/api/v1/integrations/hh-browser/connect/identifier",
        headers=auth_headers,
        json={"identifier_type": "email", "identifier": "user@example.com"},
    )
    client.post("/api/v1/integrations/hh-browser/connect/code", headers=auth_headers, json={"code": "1234"})
    cancel = client.post("/api/v1/integrations/hh-browser/connect/cancel", headers=auth_headers)

    assert cancel.status_code == 200
    assert cancel.json()["status"] == "disconnected"
    assert cancel.json()["session_present"] is False
    assert storage.deleted


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


def test_session_restore_and_check_endpoints(client, auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    probe_factory = FakeProbeFactory([True, True])
    factory.push(FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage, probe_factory)

    client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    client.post(
        "/api/v1/integrations/hh-browser/connect/identifier",
        headers=auth_headers,
        json={"identifier_type": "email", "identifier": "user@example.com"},
    )
    client.post("/api/v1/integrations/hh-browser/connect/code", headers=auth_headers, json={"code": "0000"})

    restore = client.post("/api/v1/integrations/hh-browser/session/restore", headers=auth_headers)
    check = client.post("/api/v1/integrations/hh-browser/session/check", headers=auth_headers)
    assert restore.status_code == 200
    assert restore.json()["status"] == "connected"
    assert check.status_code == 200
    assert check.json()["status"] == "connected"


def test_foreign_user_cannot_restore_owners_session(client, auth_headers, foreign_auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    probe_factory = FakeProbeFactory([True])
    factory.push(FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage, probe_factory)

    client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    client.post(
        "/api/v1/integrations/hh-browser/connect/identifier",
        headers=auth_headers,
        json={"identifier_type": "email", "identifier": "owner@example.com"},
    )
    client.post("/api/v1/integrations/hh-browser/connect/code", headers=auth_headers, json={"code": "1111"})

    foreign_restore = client.post("/api/v1/integrations/hh-browser/session/restore", headers=foreign_auth_headers)
    foreign_check = client.post("/api/v1/integrations/hh-browser/session/check", headers=foreign_auth_headers)
    assert foreign_restore.status_code == 200
    assert foreign_check.status_code == 200
    assert foreign_restore.json()["status"] == "disconnected"
    assert foreign_check.json()["status"] == "disconnected"


def test_session_validate_and_refresh_status_endpoints(client, auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    probe_factory = FakeProbeFactory([True, True])
    factory.push(FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage, probe_factory)

    client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    client.post(
        "/api/v1/integrations/hh-browser/connect/identifier",
        headers=auth_headers,
        json={"identifier_type": "email", "identifier": "check@example.com"},
    )
    client.post("/api/v1/integrations/hh-browser/connect/code", headers=auth_headers, json={"code": "1234"})

    validate = client.post("/api/v1/integrations/hh-browser/session/validate", headers=auth_headers)
    assert validate.status_code == 200
    assert validate.json()["outcome"] == "valid"
    assert validate.json()["status"] == "connected"

    refresh = client.post("/api/v1/integrations/hh-browser/session/refresh-status", headers=auth_headers)
    assert refresh.status_code == 200
    assert refresh.json()["status"] == "connected"


def test_session_require_reauth_endpoint(client, auth_headers, fake_db) -> None:
    factory = FakeFactory()
    storage = MemoryStorage()
    factory.push(FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"]))
    app.dependency_overrides[get_hh_connect_service] = _override_service(fake_db, factory, storage, FakeProbeFactory([True]))

    client.post("/api/v1/integrations/hh-browser/connect/start", headers=auth_headers, json={})
    client.post(
        "/api/v1/integrations/hh-browser/connect/identifier",
        headers=auth_headers,
        json={"identifier_type": "email", "identifier": "reauth@example.com"},
    )
    client.post("/api/v1/integrations/hh-browser/connect/code", headers=auth_headers, json={"code": "1111"})

    response = client.post("/api/v1/integrations/hh-browser/session/require-reauth", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "requires_reauth"
    assert response.json()["requires_reauth"] is True
