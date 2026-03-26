from typing import Any, Optional

from pydantic import BaseModel


class TaskStatusResponse(BaseModel):
    task_id: str
    state: str
    task_name: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: Optional[str] = None
    error_summary: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class TaskEnqueueResponse(BaseModel):
    task_id: str


class RecomputeAllTasksResponse(BaseModel):
    task_ids: dict[str, str]
