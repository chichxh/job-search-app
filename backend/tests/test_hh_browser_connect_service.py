from __future__ import annotations

import stat

from fastapi import HTTPException

from app.db import models
from app.services.hh_browser_connect_service import (
    HHBrowserAutomationError,
    HHBrowserConnectService,
    InMemoryRuntimeRegistry,
    LocalSessionStorage,
    HHSessionProbeAdapter,
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


class MemoryStorage:
    def __init__(self) -> None:
        self.saved: list[dict] = []
        self.by_ref: dict[str, dict] = {}
        self.deleted: list[str] = []

    def save(self, *, user_id: int, connection_id: int, state: dict) -> str:
        ref = f"local://hh-browser-session/u{user_id}-c{connection_id}-{len(self.saved)+1}"
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


class StaticProbe(HHSessionProbeAdapter):
    def __init__(self, *, authenticated: bool) -> None:
        self.authenticated = authenticated
        self.closed = False

    def check_authenticated(self) -> bool:
        return self.authenticated

    def close(self) -> None:
        self.closed = True


class ProbeFactory:
    def __init__(self, responses: list[bool]) -> None:
        self.responses = responses

    def create(self, *, storage_state: dict) -> StaticProbe:
        return StaticProbe(authenticated=self.responses.pop(0))


def _service(
    fake_db,
    adapters: list[FakeAdapter],
    *,
    probe_responses: list[bool] | None = None,
) -> tuple[HHBrowserConnectService, MemoryStorage]:
    storage = MemoryStorage()
    service = HHBrowserConnectService(
        fake_db,
        adapter_factory=FakeFactory(adapters),
        runtime_registry=InMemoryRuntimeRegistry(timeout_seconds=120),
        session_storage=storage,
        session_probe_factory=ProbeFactory(probe_responses or [True]),
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

    try:
        service.submit_code(user_id=1, code="1111")
        assert False, "Expected exception"
    except HTTPException as exc:
        assert exc.status_code == 400


def test_cancel_sets_disconnected(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"])
    service, storage = _service(fake_db, [adapter])

    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
    service.submit_code(user_id=1, code="1234")
    state = service.cancel(user_id=1)

    assert state.status == "disconnected"
    assert state.session_present is False
    assert storage.deleted
    action_runs = fake_db.query(models.HHAutomationActionRun).all()
    assert any(item.action_type == "connect" and item.status == "completed" for item in action_runs)
    assert any(item.action_type == "connect_cancel" and item.status == "cancelled" for item in action_runs)


def test_unknown_step_detection_returns_failed_with_normalized_error(fake_db) -> None:
    service, _ = _service(fake_db, [FakeAdapter(["failed"])])

    state = service.start(user_id=1)

    assert state.status == "failed"
    assert state.last_error_code == "page_not_recognized"
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
    try:
        service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
        assert False, "Expected timeout exception"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail["code"] == "session_timeout"

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


def test_restore_from_stored_state_marks_connected(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"])
    service, _ = _service(fake_db, [adapter], probe_responses=[True])

    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
    service.submit_code(user_id=1, code="1234")

    restored = service.restore_session(user_id=1)

    assert restored.status == "connected"
    assert restored.requires_reauth is False


def test_restore_with_missing_storage_ref_requires_reauth(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"])
    service, storage = _service(fake_db, [adapter], probe_responses=[True])

    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
    service.submit_code(user_id=1, code="1234")
    stored_ref = next(iter(storage.by_ref))
    storage.by_ref.pop(stored_ref, None)

    restored = service.restore_session(user_id=1)

    assert restored.status == "requires_reauth"
    assert restored.last_error_code == "session_state_not_found"
    assert restored.session_present is False


def test_restore_with_corrupted_storage_requires_reauth(fake_db) -> None:
    class CorruptedStorage(MemoryStorage):
        def load(self, *, ref: str) -> dict:
            raise ValueError("corrupted")

    storage = CorruptedStorage()
    service = HHBrowserConnectService(
        fake_db,
        adapter_factory=FakeFactory([FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"])]),
        runtime_registry=InMemoryRuntimeRegistry(timeout_seconds=120),
        session_storage=storage,
        session_probe_factory=ProbeFactory([True]),
    )

    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
    service.submit_code(user_id=1, code="1234")

    restored = service.restore_session(user_id=1)
    assert restored.status == "requires_reauth"
    assert restored.last_error_code == "session_state_corrupted"


def test_validate_logged_out_sets_requires_reauth(fake_db) -> None:
    adapter = FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"])
    service, _ = _service(fake_db, [adapter], probe_responses=[False])

    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
    service.submit_code(user_id=1, code="1234")

    outcome = service.validate_session(user_id=1)
    assert outcome["outcome"] == "logged_out"
    assert outcome["status"] == "requires_reauth"
    assert outcome["requires_reauth"] is True


def test_failed_start_returns_safe_message_and_closes_adapter(fake_db) -> None:
    class FailingAdapter(FakeAdapter):
        def __init__(self) -> None:
            super().__init__([])

        def open_login_page(self) -> str:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "debug details with dom dump")

    adapter = FailingAdapter()
    service, _ = _service(fake_db, [adapter])

    try:
        service.start(user_id=1)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail["code"] == "transient_navigation"
        assert exc.detail["message"] == "HH login page is temporarily unavailable. Retry in a moment."

    assert adapter.closed is True


def test_local_session_storage_enforces_secure_permissions_and_deletes(tmp_path) -> None:
    storage = LocalSessionStorage(base_dir=str(tmp_path / "sessions"))
    ref = storage.save(user_id=1, connection_id=2, state={"cookies": [{"name": "hh_sid", "value": "x"}], "origins": []})
    path = storage._resolve_ref(ref)  # noqa: SLF001

    assert path.exists()
    dir_mode = stat.S_IMODE(path.parent.stat().st_mode)
    file_mode = stat.S_IMODE(path.stat().st_mode)
    assert dir_mode == 0o700
    assert file_mode == 0o600

    loaded = storage.load(ref=ref)
    assert loaded["cookies"][0]["name"] == "hh_sid"

    storage.delete(ref=ref)
    assert not path.exists()


def test_validate_missing_storage_keeps_disconnected(fake_db) -> None:
    service, _ = _service(fake_db, [FakeAdapter(["awaiting_identifier"])], probe_responses=[True])

    outcome = service.validate_session(user_id=1)
    assert outcome["outcome"] == "invalid_storage"
    assert outcome["status"] == "disconnected"
    assert outcome["last_error_code"] == "session_state_missing"


def test_transient_validation_failure_marks_failed_without_wiping_session(fake_db) -> None:
    class FailingProbeFactory:
        def create(self, *, storage_state: dict):
            class _Probe:
                def check_authenticated(self) -> bool:
                    raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Timed out while checking HH session")

                def close(self) -> None:
                    return None

            return _Probe()

    storage = MemoryStorage()
    service = HHBrowserConnectService(
        fake_db,
        adapter_factory=FakeFactory([FakeAdapter(["awaiting_identifier", "awaiting_code", "connected"])]),
        runtime_registry=InMemoryRuntimeRegistry(timeout_seconds=120),
        session_storage=storage,
        session_probe_factory=FailingProbeFactory(),
    )
    service.start(user_id=1)
    service.submit_identifier(user_id=1, identifier_type="email", identifier="user@example.com")
    service.submit_code(user_id=1, code="1234")

    outcome = service.validate_session(user_id=1)
    assert outcome["outcome"] == "network/transient_failure"
    assert outcome["status"] == "failed"
    assert outcome["requires_reauth"] is False
    assert outcome["session_present"] is True
