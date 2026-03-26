from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import models
from app.db.session import get_db

os.environ.setdefault("EMBEDDING_PROVIDER", "localhash")
from app.main import app  # noqa: E402

from tests.helpers import FakeExecuteResult

class FakeQuery:
    def __init__(self, items: list[Any]):
        self._items = items

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self):
        self._storage: dict[type, dict[int, Any]] = {}
        self._next_id: dict[type, int] = {}
        self._execute_queue: list[FakeExecuteResult] = []

    def queue_execute_results(self, *results: FakeExecuteResult):
        self._execute_queue.extend(results)

    def add(self, item: Any):
        model = type(item)
        next_id = self._next_id.get(model, 1)
        if getattr(item, "id", None) is None:
            item.id = next_id
            self._next_id[model] = next_id + 1

        now = datetime.now(timezone.utc)
        if getattr(item, "created_at", None) is None:
            item.created_at = now
        if hasattr(item, "updated_at") and getattr(item, "updated_at", None) is None:
            item.updated_at = now

        self._storage.setdefault(model, {})[item.id] = item

    def get(self, model: type, item_id: int):
        return self._storage.get(model, {}).get(item_id)

    def query(self, model: type):
        items = list(self._storage.get(model, {}).values())
        return FakeQuery(items)

    def execute(self, *_args, **_kwargs):
        if self._execute_queue:
            return self._execute_queue.pop(0)
        return FakeExecuteResult()

    def commit(self):
        return None

    def refresh(self, _item: Any):
        return None

    def delete(self, item: Any):
        model = type(item)
        if model in self._storage:
            self._storage[model].pop(item.id, None)


@pytest.fixture()
def fake_db():
    db = FakeDB()

    profile = models.Profile(
        resume_text="Python backend engineer",
        title="Backend Engineer",
        full_name="Test Candidate",
        city="Moscow",
    )
    db.add(profile)

    vacancy = models.Vacancy(
        source="hh",
        external_id="hh-1",
        title="Senior Backend Engineer",
        company_name="Acme",
        location="Remote",
        description="Python + FastAPI",
        url="https://example.com/vacancy/1",
    )
    db.add(vacancy)

    return db


@pytest.fixture()
def client(fake_db, monkeypatch):
    from app.api.routers import profiles

    monkeypatch.setattr(profiles.build_profile_embedding, "delay", lambda *_args, **_kwargs: None)

    def _override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
