from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileLinkCreate(BaseModel):
    type: str
    url: str
    label: Optional[str] = None


class ProfileLinkUpdate(BaseModel):
    type: Optional[str] = None
    url: Optional[str] = None
    label: Optional[str] = None


class ProfileLinkRead(BaseModel):
    id: int
    profile_id: int
    type: str
    url: str
    label: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
