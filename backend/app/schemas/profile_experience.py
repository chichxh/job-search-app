from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileExperienceCreate(BaseModel):
    company_name: str
    position_title: str
    location: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    is_current: bool = False
    responsibilities_text: str
    achievements_text: str
    tech_stack_text: Optional[str] = None
    employment_type: Optional[str] = None


class ProfileExperienceUpdate(BaseModel):
    company_name: Optional[str] = None
    position_title: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    responsibilities_text: Optional[str] = None
    achievements_text: Optional[str] = None
    tech_stack_text: Optional[str] = None
    employment_type: Optional[str] = None


class ProfileExperienceRead(BaseModel):
    id: int
    profile_id: int
    company_name: str
    position_title: str
    location: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    is_current: bool
    responsibilities_text: str
    achievements_text: str
    tech_stack_text: Optional[str] = None
    employment_type: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
