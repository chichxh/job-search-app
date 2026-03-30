from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class ResumeExtractionResponse(BaseModel):
    filename: str
    content_type: str | None = None
    detected_type: str = Field(description="Normalized detected file type")
    extracted_text: str
    text_length: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    extractor_used: str
    import_ready: bool


class ResumeProfileDraftExperience(BaseModel):
    company_name: str
    position_title: str
    location: str | None = None
    start_date: date | str
    end_date: date | str | None = None
    is_current: bool = False
    description: str | None = None
    achievements_text: str | None = None
    tech_stack_text: str | None = None
    employment_type: str | None = None


class ResumeProfileDraftSkill(BaseModel):
    name_raw: str
    normalized_key: str | None = None
    category: str = "hard_skill"
    level: str = "intermediate"
    years: float | None = None
    last_used_year: int | None = None
    is_primary: bool = False
    evidence_text: str | None = None


class ResumeProfileDraftLanguage(BaseModel):
    language: str
    level: str = "unknown"


class ResumeProfileDraftLink(BaseModel):
    type: str
    url: str
    label: str | None = None


class ResumeProfileDraftPayload(BaseModel):
    full_name: str | None = None
    title: str | None = None
    location: str | None = None
    summary_about: str | None = None
    salary_min: int | None = Field(default=None, ge=0)
    experiences: list[ResumeProfileDraftExperience] = Field(default_factory=list)
    skills: list[ResumeProfileDraftSkill] = Field(default_factory=list)
    languages: list[ResumeProfileDraftLanguage] = Field(default_factory=list)
    links: list[ResumeProfileDraftLink] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    quality_hints: dict[str, Any] = Field(default_factory=dict)


class ResumeImportParseRequest(BaseModel):
    extracted_text: str = Field(min_length=1)


class ResumeImportParseResponse(BaseModel):
    draft: ResumeProfileDraftPayload
    parser_metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    applyability: dict[str, Any] = Field(default_factory=dict)


class ResumeImportApplyRequest(BaseModel):
    draft: ResumeProfileDraftPayload
    update_main_fields: bool = True
    replace_sections: list[Literal["experiences", "skills", "languages", "links"]] = Field(
        default_factory=lambda: ["experiences", "skills", "languages", "links"]
    )


class ResumeImportApplyResponse(BaseModel):
    profile_id: int
    updated_fields: list[str] = Field(default_factory=list)
    replaced_sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
