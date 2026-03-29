from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class HHOAuthStartResponse(BaseModel):
    authorize_url: str


class HHOAuthConnectionStatus(BaseModel):
    connected: bool
    connected_at: Optional[datetime] = None
    token_expires_at: Optional[datetime] = None
    hh_user_id: Optional[str] = None
    hh_resume_id: Optional[str] = None
    last_imported_at: Optional[datetime] = None


class HHResumeOption(BaseModel):
    id: str
    title: str
    updated_at: Optional[datetime] = None


class HHProfileImportRequest(BaseModel):
    consent: bool = Field(default=False)
    resume_id: Optional[str] = None


class HHProfileImportJSONRequest(BaseModel):
    consent: bool = Field(default=False)
    payload: dict[str, Any]
    resume_id: Optional[str] = None


class HHProfileImportResponse(BaseModel):
    profile_id: int
    resume_id: str
    imported_at: datetime
    updated_fields: list[str] = Field(default_factory=list)
    replaced_sections: list[str] = Field(default_factory=list)


class HHProviderError(BaseModel):
    detail: str

    model_config = ConfigDict(extra="ignore")
