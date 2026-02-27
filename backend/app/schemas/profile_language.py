from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileLanguageCreate(BaseModel):
    language: str
    level: str


class ProfileLanguageUpdate(BaseModel):
    language: Optional[str] = None
    level: Optional[str] = None


class ProfileLanguageRead(BaseModel):
    id: int
    profile_id: int
    language: str
    level: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
