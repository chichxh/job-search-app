from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileProjectCreate(BaseModel):
    name: str
    role: Optional[str] = None
    description_text: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    tech_stack_text: Optional[str] = None
    url: Optional[str] = None


class ProfileProjectUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description_text: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    tech_stack_text: Optional[str] = None
    url: Optional[str] = None


class ProfileProjectRead(BaseModel):
    id: int
    profile_id: int
    name: str
    role: Optional[str] = None
    description_text: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    tech_stack_text: Optional[str] = None
    url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
