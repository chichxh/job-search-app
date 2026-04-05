from datetime import datetime

from pydantic import BaseModel, Field, field_validator

HH_BROWSER_STATUSES = (
    "disconnected",
    "connecting",
    "awaiting_code",
    "connected",
    "requires_reauth",
    "failed",
)


class HHBrowserConnectInitRequest(BaseModel):
    session_state_ref: str | None = Field(default=None, max_length=255)
    session_expires_at: datetime | None = None


class HHBrowserMarkAwaitingCodeRequest(BaseModel):
    requires_reauth: bool = False


class HHBrowserMarkConnectedRequest(BaseModel):
    session_state_ref: str | None = Field(default=None, max_length=255)
    session_expires_at: datetime | None = None


class HHBrowserMarkFailedRequest(BaseModel):
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str = Field(min_length=1, max_length=500)
    requires_reauth: bool = False


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
