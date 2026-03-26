from __future__ import annotations

from types import SimpleNamespace


def test_task_status_success_contains_observability_fields(client, monkeypatch):
    fake_result = SimpleNamespace(
        state="SUCCESS",
        info={"task_name": "app.tasks.hh_import_tasks.import_hh_vacancies_task", "started_at": "2026-03-26T10:00:00+00:00"},
        result={
            "saved_count": 5,
            "_task": {
                "task_name": "app.tasks.hh_import_tasks.import_hh_vacancies_task",
                "started_at": "2026-03-26T10:00:00+00:00",
                "finished_at": "2026-03-26T10:00:07+00:00",
                "duration_ms": 7000,
                "message": "HH import finished",
            },
        },
        date_done=None,
    )
    monkeypatch.setattr("app.api.routers.imports.celery_app.AsyncResult", lambda _task_id: fake_result)

    response = client.get("/api/v1/tasks/task-123")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-123"
    assert payload["state"] == "SUCCESS"
    assert payload["task_name"] == "app.tasks.hh_import_tasks.import_hh_vacancies_task"
    assert payload["started_at"] == "2026-03-26T10:00:00+00:00"
    assert payload["finished_at"] == "2026-03-26T10:00:07+00:00"
    assert payload["message"] == "HH import finished"


def test_task_status_failure_contains_error_summary(client, monkeypatch):
    fake_result = SimpleNamespace(
        state="FAILURE",
        info={},
        result=ValueError("boom failure\ntraceback line"),
        date_done=None,
    )
    monkeypatch.setattr("app.api.routers.imports.celery_app.AsyncResult", lambda _task_id: fake_result)

    response = client.get("/api/v1/tasks/task-err")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "FAILURE"
    assert payload["error"] == "boom failure\ntraceback line"
    assert payload["error_summary"] == "boom failure"
