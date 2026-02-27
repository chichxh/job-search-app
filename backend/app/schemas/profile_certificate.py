from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProfileCertificateCreate(BaseModel):
    name: str
    issuer: str
    issued_at: Optional[date] = None
    expires_at: Optional[date] = None
    url: Optional[str] = None


class ProfileCertificateUpdate(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    issued_at: Optional[date] = None
    expires_at: Optional[date] = None
    url: Optional[str] = None


class ProfileCertificateRead(BaseModel):
    id: int
    profile_id: int
    name: str
    issuer: str
    issued_at: Optional[date] = None
    expires_at: Optional[date] = None
    url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
