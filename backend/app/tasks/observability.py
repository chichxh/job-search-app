from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from celery.app.task import Task

from app.utils.log_safety import safe_error_summary


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def task_name(task: Task, fallback: str) -> str:
    return getattr(task, "name", "") or fallback


def mark_task_started(task: Task, *, name: str, message: str, extra: dict[str, Any] | None = None) -> str:
    started_at = now_utc_iso()
    meta = {
        "task_name": name,
        "message": message,
        "started_at": started_at,
    }
    if extra:
        meta.update(extra)
    task.update_state(state="STARTED", meta=meta)
    return started_at


def success_meta(name: str, started_at: str, timer_started: float, message: str) -> dict[str, Any]:
    finished_at = now_utc_iso()
    duration_ms = round((perf_counter() - timer_started) * 1000, 2)
    return {
        "_task": {
            "task_name": name,
            "message": message,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
        }
    }


def failure_summary(exc: Exception) -> str:
    return safe_error_summary(exc)
