from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileSkillCreate(BaseModel):
    name_raw: str
    normalized_key: Optional[str] = None
    category: str
    level: str
    years: Optional[float] = None
    last_used_year: Optional[int] = None
    is_primary: bool = False
    evidence_text: Optional[str] = None


class ProfileSkillUpdate(BaseModel):
    name_raw: Optional[str] = None
    normalized_key: Optional[str] = None
    category: Optional[str] = None
    level: Optional[str] = None
    years: Optional[float] = None
    last_used_year: Optional[int] = None
    is_primary: Optional[bool] = None
    evidence_text: Optional[str] = None


class ProfileSkillRead(BaseModel):
    id: int
    profile_id: int
    name_raw: str
    normalized_key: Optional[str] = None
    category: str
    level: str
    years: Optional[float] = None
    last_used_year: Optional[int] = None
    is_primary: bool
    evidence_text: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
