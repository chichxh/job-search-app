from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

EmploymentType = Literal["full_time", "part_time", "contract", "internship", "project", "volunteer"]
ScheduleType = Literal["full_day", "shift", "flexible", "remote", "hybrid"]
SeniorityLevel = Literal["intern", "junior", "middle", "senior", "lead", "principal"]


class ProfileCreate(BaseModel):
    title: Optional[str] = None
    resume_text: str
    skills_text: Optional[str] = None
    location: Optional[str] = None
    remote_ok: Optional[bool] = True
    relocation_ok: Optional[bool] = False
    salary_min: Optional[int] = None

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None

    city: Optional[str] = None
    country: Optional[str] = None
    metro: Optional[str] = None

    citizenship: Optional[str] = None
    work_authorization_country: Optional[str] = None
    needs_sponsorship: Optional[bool] = False

    available_from: Optional[date] = None
    notice_period_days: Optional[int] = None

    preferred_employment: Optional[EmploymentType] = None
    preferred_schedule: Optional[ScheduleType] = None

    preferred_industries: list[str] = Field(default_factory=list)
    preferred_company_types: list[str] = Field(default_factory=list)
    interest_tags: list[str] = Field(default_factory=list)
    preferred_tech: list[str] = Field(default_factory=list)
    excluded_tech: list[str] = Field(default_factory=list)
    team_preferences_json: dict[str, Any] = Field(default_factory=dict)

    summary_about: Optional[str] = None
    seniority_level: Optional[SeniorityLevel] = None
    years_total: Optional[float] = None


class ProfileUpdate(BaseModel):
    title: Optional[str] = None
    resume_text: Optional[str] = None
    skills_text: Optional[str] = None
    location: Optional[str] = None
    remote_ok: Optional[bool] = None
    relocation_ok: Optional[bool] = None
    salary_min: Optional[int] = None

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None

    city: Optional[str] = None
    country: Optional[str] = None
    metro: Optional[str] = None

    citizenship: Optional[str] = None
    work_authorization_country: Optional[str] = None
    needs_sponsorship: Optional[bool] = None

    available_from: Optional[date] = None
    notice_period_days: Optional[int] = None

    preferred_employment: Optional[EmploymentType] = None
    preferred_schedule: Optional[ScheduleType] = None

    preferred_industries: Optional[list[str]] = None
    preferred_company_types: Optional[list[str]] = None
    interest_tags: Optional[list[str]] = None
    preferred_tech: Optional[list[str]] = None
    excluded_tech: Optional[list[str]] = None
    team_preferences_json: Optional[dict[str, Any]] = None

    summary_about: Optional[str] = None
    seniority_level: Optional[SeniorityLevel] = None
    years_total: Optional[float] = None


class ProfileRead(BaseModel):
    id: int
    title: Optional[str] = None
    resume_text: str
    skills_text: Optional[str] = None
    location: Optional[str] = None
    remote_ok: bool = True
    relocation_ok: bool = False
    salary_min: Optional[int] = None

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None

    city: Optional[str] = None
    country: Optional[str] = None
    metro: Optional[str] = None

    citizenship: Optional[str] = None
    work_authorization_country: Optional[str] = None
    needs_sponsorship: bool = False

    available_from: Optional[date] = None
    notice_period_days: Optional[int] = None

    preferred_employment: Optional[EmploymentType] = None
    preferred_schedule: Optional[ScheduleType] = None

    preferred_industries: list[str] = Field(default_factory=list)
    preferred_company_types: list[str] = Field(default_factory=list)
    interest_tags: list[str] = Field(default_factory=list)
    preferred_tech: list[str] = Field(default_factory=list)
    excluded_tech: list[str] = Field(default_factory=list)
    team_preferences_json: dict[str, Any] = Field(default_factory=dict)

    summary_about: Optional[str] = None
    seniority_level: Optional[SeniorityLevel] = None
    years_total: Optional[float] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
