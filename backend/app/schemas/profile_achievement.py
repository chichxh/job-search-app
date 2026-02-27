from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileAchievementCreate(BaseModel):
    title: str
    description_text: str
    metric: Optional[str] = None
    achieved_at: Optional[date] = None
    related_experience_id: Optional[int] = None
    related_project_id: Optional[int] = None


class ProfileAchievementUpdate(BaseModel):
    title: Optional[str] = None
    description_text: Optional[str] = None
    metric: Optional[str] = None
    achieved_at: Optional[date] = None
    related_experience_id: Optional[int] = None
    related_project_id: Optional[int] = None


class ProfileAchievementRead(BaseModel):
    id: int
    profile_id: int
    title: str
    description_text: str
    metric: Optional[str] = None
    achieved_at: Optional[date] = None
    related_experience_id: Optional[int] = None
    related_project_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
