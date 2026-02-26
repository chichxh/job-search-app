from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileCreate(BaseModel):
    title: Optional[str] = None
    resume_text: str
    skills_text: Optional[str] = None
    location: Optional[str] = None
    remote_ok: Optional[bool] = True
    relocation_ok: Optional[bool] = False
    salary_min: Optional[int] = None


class ProfileUpdate(BaseModel):
    title: Optional[str] = None
    resume_text: Optional[str] = None
    skills_text: Optional[str] = None
    location: Optional[str] = None
    remote_ok: Optional[bool] = None
    relocation_ok: Optional[bool] = None
    salary_min: Optional[int] = None


class ProfileRead(BaseModel):
    id: int
    title: Optional[str] = None
    resume_text: str
    skills_text: Optional[str] = None
    location: Optional[str] = None
    remote_ok: bool = True
    relocation_ok: bool = False
    salary_min: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
