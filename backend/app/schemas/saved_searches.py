from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.imports import AllowedExtraParamValue


class SavedSearchBase(BaseModel):
    text: str = Field(min_length=1, max_length=255)
    area: str | None = Field(default=None, max_length=50)
    schedule: str | None = Field(default=None, max_length=50)
    experience: str | None = Field(default=None, max_length=50)
    salary_from: int | None = Field(default=None, ge=0)
    salary_to: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)
    filters_json: dict[str, AllowedExtraParamValue] = Field(default_factory=dict)
    per_page: int = Field(default=20, ge=1, le=100)
    pages_limit: int = Field(default=3, ge=1, le=20)


class SavedSearchCreate(SavedSearchBase):
    pass


class SavedSearchUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=255)
    area: str | None = Field(default=None, max_length=50)
    schedule: str | None = Field(default=None, max_length=50)
    experience: str | None = Field(default=None, max_length=50)
    salary_from: int | None = Field(default=None, ge=0)
    salary_to: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)
    filters_json: dict[str, AllowedExtraParamValue] | None = None
    per_page: int | None = Field(default=None, ge=1, le=100)
    pages_limit: int | None = Field(default=None, ge=1, le=20)
    cursor_page: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class SavedSearchResponse(SavedSearchBase):
    id: int
    cursor_page: int
    is_active: bool
    last_sync_at: datetime | None
    last_seen_published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SavedSearchSyncResponse(BaseModel):
    task_id: str
