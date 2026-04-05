from __future__ import annotations

from app.db import models
from app.services.hh_browser_connect_service import (
    HHBrowserAutomationError,
    HHBrowserConnectService,
    InMemoryRuntimeRegistry,
    LocalSessionStorage,
)


class FakeAdapter:
    def __init__(self, steps: list[str]) -> None:
        self.steps = steps
        self.closed = False
        self.identifier_payloads: list[tuple[str, str]] = []
        self.password_payloads: list[str] = []
        self.code_payloads: list[str] = []

    def open_login_page(self) -> str:
        return self.steps.pop(0)

    def submit_identifier(self, *, identifier: str, identifier_type: str) -> str:
        self.identifier_payloads.append((identifier_type, identifier))
        return self.steps.pop(0)

    def submit_password(self, *, password: str) -> str:
        self.password_payloads.append(password)
        return self.steps.pop(0)

    def submit_code(self, *, code: str) -> str:
        self.code_payloads.append(code)
        return self.steps.pop(0)

    def export_storage_state(self) -> dict:
        return {"cookies": [{"name": "hh_sid", "value": "masked"}]}

    def close(self) -> None:
        self.closed = True

    def safe_debug_summary(self) -> dict:
        return {"url": "https://hh.ru/account/login", "title": "HH Login"}


class FakeFactory:
    def __init__(self, adapters: list[FakeAdapter]) -> None:
        self.adapters = adapters

    def create(self) -> FakeAdapter:
        return self.adapters.pop(0)


class MemoryStorage(LocalSessionStorage):
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def save(self, *, user_id: int, connection_id: int, state: dict) -> str:
        self.saved.append({"user_id": user_id, "connection_id": connection_id, "state": state})
        return f"local://hh-browser-session/u{user_id}-c{connection_id}"


def _service(fake_db, adapters: list[FakeAdapter]) -> tuple[HHBrowserConnectService, MemoryStorage]:
    storage = MemoryStorage()
    service = HHBrowserConnectService(
        fake_db,
        adapter_factory=FakeFactory(adapters),
        runtime_registry=InMemoryRuntimeRegistry(timeout_seconds=120),
        session_storage=storage,
    )
    return service, storage


def test_start_to_awaiting_identifier(fake_db) -> None:
    service, _ = _service(fake_db, [FakeAdapter(["awaiting_identifier"])])

    state = service.start(user_id=1)

    assert state.status == "awaiting_identifier"


def test_identifier_to_awaiting_password(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier", "awaiting_password"])
    service, _ = _service(fake_db, [adapter])

    service.start(user_id=1)
    state = service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")

    assert state.status == "awaiting_password"
    assert adapter.identifier_payloads == [("email", "user@example.com")]


def test_password_to_awaiting_code(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier", "awaiting_password", "awaiting_code"])
    service, _ = _service(fake_db, [adapter])

    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="phone", identifier="+79998887766")
    state = service.submit_password(user_id=1, password="super-secret")

    assert state.status == "awaiting_code"
    assert adapter.password_payloads == ["super-secret"]


def test_code_to_connected_persists_session_reference(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"])
    service, storage = _service(fake_db, [adapter])

    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
    state = service.submit_code(user_id=1, code="1234")

    assert state.status == "connected"
    assert storage.saved
    stored = next((item for item in fake_db.query(models.HHBrowserConnection).all() if item.user_id == 1), None)
    assert stored is not None
    assert stored.session_state_ref is not None


def test_invalid_transition_returns_http_400(fake_db) -> None:
    service, _ = _service(fake_db, [FakeAdapter(["awaiting_identifier"])])

    service.start(user_id=1)

    from fastapi import HTTPException

    try:
        service.submit_code(user_id=1, code="1111")
        assert False, "Expected exception"
    except HTTPException as exc:
        assert exc.status_code == 400


def test_cancel_sets_disconnected(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier"])
    service, _ = _service(fake_db, [adapter])

    service.start(user_id=1)
    state = service.cancel(user_id=1)

    assert state.status == "disconnected"
    assert adapter.closed is True


def test_unknown_step_detection_returns_failed_with_normalized_error(fake_db) -> None:
    service, _ = _service(fake_db, [FakeAdapter(["failed"])])

    state = service.start(user_id=1)

    assert state.status == "failed"
    assert state.last_error_code == "UNRECOGNIZED_STATE"
    assert "Unable to determine HH login step" in (state.last_error_message or "")


def test_timeout_handling_marks_connection_failed(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier"])
    service = HHBrowserConnectService(
        fake_db,
        adapter_factory=FakeFactory([adapter]),
        runtime_registry=InMemoryRuntimeRegistry(timeout_seconds=0),
        session_storage=MemoryStorage(),
    )

    service.start(user_id=1)
    from fastapi import HTTPException

    try:
        service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
        assert False, "Expected timeout exception"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail["code"] == "SESSION_TIMEOUT"

    state = service.get_state(user_id=1)
    assert state.status == "failed"
    assert state.debug.runtime_session_alive is False


def test_retryable_transient_failure_succeeds(fake_db) -> None:
    class RetryAdapter(FakeAdapter):
        def __init__(self) -> None:
            super().__init__(["awaiting_identifier"])
            self.calls = 0

        def open_login_page(self) -> str:
            self.calls += 1
            if self.calls == 1:
                raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Temporary HH load issue")
            return "awaiting_identifier"

    adapter = RetryAdapter()
    service, _ = _service(fake_db, [adapter])

    state = service.start(user_id=1)

    assert state.status == "awaiting_identifier"
    assert adapter.calls == 2


def test_connected_state_survives_restore_when_session_reference_exists(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"])
    service, _ = _service(fake_db, [adapter])

    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
    connected = service.submit_code(user_id=1, code="1234")
    restored = service.get_state(user_id=1)

    assert connected.status == "connected"
    assert restored.status == "connected"
    assert restored.session_present is True
