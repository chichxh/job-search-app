from typing import Any, Optional

from pydantic import BaseModel


class TaskStatusResponse(BaseModel):
    task_id: str
    state: str
    result: Optional[Any] = None
    error: Optional[str] = None
