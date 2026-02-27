from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileEducationCreate(BaseModel):
    institution: str
    degree_level: str
    field_of_study: str
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description_text: Optional[str] = None
    gpa: Optional[float] = None


class ProfileEducationUpdate(BaseModel):
    institution: Optional[str] = None
    degree_level: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description_text: Optional[str] = None
    gpa: Optional[float] = None


class ProfileEducationRead(BaseModel):
    id: int
    profile_id: int
    institution: str
    degree_level: str
    field_of_study: str
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description_text: Optional[str] = None
    gpa: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
