from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CoverLetterVersionCreate(BaseModel):
    vacancy_id: Optional[int] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    content_text: str
    source: str = "user"
    status: str = "draft"


class CoverLetterVersionUpdate(BaseModel):
    vacancy_id: Optional[int] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    content_text: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None


class CoverLetterVersionRead(BaseModel):
    id: int
    profile_id: int
    vacancy_id: Optional[int] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    content_text: str
    source: str
    status: str
    created_at: datetime
    approved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
