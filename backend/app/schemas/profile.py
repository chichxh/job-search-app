from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileCreate(BaseModel):
    title: Optional[str] = None
    resume_text: str
    skills_text: Optional[str] = None


class ProfileUpdate(BaseModel):
    title: Optional[str] = None
    resume_text: Optional[str] = None
    skills_text: Optional[str] = None


class ProfileRead(BaseModel):
    id: int
    title: Optional[str] = None
    resume_text: str
    skills_text: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
