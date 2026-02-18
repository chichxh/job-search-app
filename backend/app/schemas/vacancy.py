from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class VacancyCreate(BaseModel):
    source: str
    external_id: str
    title: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    status: str = "open"


class VacancyUpdate(BaseModel):
    source: Optional[str] = None
    external_id: Optional[str] = None
    title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None


class VacancyRead(BaseModel):
    id: int
    source: str
    external_id: str
    title: str
    company_name: Optional[str] = None
    location: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
