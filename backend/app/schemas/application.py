from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

ApplicationStatus = Literal[
    "saved",
    "planned",
    "applied",
    "hr_screen",
    "tech_interview",
    "test_task",
    "offer",
    "rejected",
    "archived",
]


HHExternalApplyStatus = Literal[
    "submitted",
    "already_applied",
]


class ApplicationCreate(BaseModel):
    vacancy_id: int
    status: ApplicationStatus = "saved"
    note: Optional[str] = None
    resume_version_id: Optional[int] = None
    cover_letter_version_id: Optional[int] = None


class ApplicationUpdate(BaseModel):
    note: Optional[str] = None
    resume_version_id: Optional[int] = None
    cover_letter_version_id: Optional[int] = None


class ApplicationStatusChange(BaseModel):
    status: ApplicationStatus
    note: Optional[str] = None


class ApplicationRead(BaseModel):
    id: int
    profile_id: int
    vacancy_id: int
    status: ApplicationStatus
    note: Optional[str] = None
    resume_version_id: Optional[int] = None
    cover_letter_version_id: Optional[int] = None
    last_hh_apply_run_id: Optional[int] = None
    hh_managed_resume_id: Optional[int] = None
    external_apply_status: Optional[HHExternalApplyStatus] = None
    last_external_apply_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationStatusHistoryRead(BaseModel):
    id: int
    application_id: int
    from_status: Optional[ApplicationStatus] = None
    to_status: ApplicationStatus
    note: Optional[str] = None
    hh_apply_run_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
