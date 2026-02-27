from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ResumeVersionCreate(BaseModel):
    vacancy_id: Optional[int] = None
    title: Optional[str] = None
    content_text: str
    format: str = "plain"
    source: str = "user"
    status: str = "draft"


class ResumeVersionUpdate(BaseModel):
    vacancy_id: Optional[int] = None
    title: Optional[str] = None
    content_text: Optional[str] = None
    format: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None


class ResumeVersionRead(BaseModel):
    id: int
    profile_id: int
    vacancy_id: Optional[int] = None
    title: Optional[str] = None
    content_text: str
    format: str
    source: str
    status: str
    created_at: datetime
    approved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
