from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class HHBrowserConnectionDebug(BaseModel):
    current_detected_step: Literal["awaiting_identifier", "awaiting_password", "awaiting_code", "connected", "failed"] | None = None
    last_transition_at: datetime | None = None
    runtime_session_alive: bool = False


class HHBrowserConnectionSummary(BaseModel):
    status: str
    requires_reauth: bool
    last_authenticated_at: datetime | None = None
    last_checked_at: datetime | None = None
    session_present: bool
    last_error_code: str | None = None
    last_error_message: str | None = None
    updated_at: datetime
    debug: HHBrowserConnectionDebug

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in HH_BROWSER_STATUSES:
            raise ValueError("Unsupported status")
        return value


HH_SESSION_VALIDATION_OUTCOMES = (
    "valid",
    "expired",
    "logged_out",
    "invalid_storage",
    "network/transient_failure",
)


class HHBrowserSessionValidationResponse(BaseModel):
    outcome: str
    status: str
    requires_reauth: bool
    last_checked_at: datetime | None = None
    session_present: bool
    last_error_code: str | None = None
    last_error_message: str | None = None

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: str) -> str:
        if value not in HH_SESSION_VALIDATION_OUTCOMES:
            raise ValueError("Unsupported validation outcome")
        return value


HH_MANAGED_RESUME_STATUSES = ("draft_local", "creating", "created", "failed", "stale")


class HHCreateTargetedResumeRequest(BaseModel):
    profile_id: int
    vacancy_id: int | None = None
    source_resume_version_id: int | None = None
    target_title: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=3000)
    skills_focus: list[str] = Field(default_factory=list, max_length=30)
    include_skill_levels: bool = False
    max_experiences: int = Field(default=4, ge=1, le=10)
    dry_run: bool = False


class HHTargetedResumePayload(BaseModel):
    profession_title: str
    summary: str
    education: list[dict[str, Any]]
    skills: list[str]
    skill_level_hints: dict[str, str]
    work_experience: list[dict[str, Any]]
    targeted_emphasis: list[str]


class HHManagedResumeRead(BaseModel):
    id: int
    user_id: int
    profile_id: int
    source_resume_version_id: int | None = None
    vacancy_id: int | None = None
    hh_resume_external_id: str | None = None
    hh_resume_url: str | None = None
    title: str | None = None
    status: str
    last_synced_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in HH_MANAGED_RESUME_STATUSES:
            raise ValueError("Unsupported status")
        return value


class HHCreateTargetedResumeResponse(BaseModel):
    managed_resume: HHManagedResumeRead
    payload_preview: HHTargetedResumePayload | None = None
