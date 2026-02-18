from typing import Optional

from pydantic import BaseModel, Field


class HHImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=255)
    area: Optional[int] = None
    per_page: int = Field(default=20, ge=1, le=100)
    pages_limit: int = Field(default=3, ge=1, le=20)
    fetch_details: bool = True


class HHImportTaskResponse(BaseModel):
    task_id: str
