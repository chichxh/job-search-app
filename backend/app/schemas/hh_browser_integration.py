from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

HH_BROWSER_STATUSES = (
    "disconnected",
    "connecting",
    "awaiting_identifier",
    "awaiting_password",
    "awaiting_code",
    "connected",
    "requires_reauth",
    "failed",
)

HH_IDENTIFIER_TYPES = ("phone", "email")


class HHBrowserConnectStartRequest(BaseModel):
    force_restart: bool = False


class HHBrowserSubmitIdentifierRequest(BaseModel):
    identifier_type: Literal["phone", "email"]
    identifier: str = Field(min_length=3, max_length=255)


class HHBrowserSubmitPasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=255)


class HHBrowserSubmitCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class HHBrowserConnectionSummary(BaseModel):
    status: str
    requires_reauth: bool
    last_authenticated_at: datetime | None = None
    last_checked_at: datetime | None = None
    session_present: bool
    last_error_code: str | None = None
    last_error_message: str | None = None
    updated_at: datetime

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in HH_BROWSER_STATUSES:
            raise ValueError("Unsupported status")
        return value
