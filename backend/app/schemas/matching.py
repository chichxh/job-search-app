from typing import Any

from pydantic import BaseModel


class RecommendationItem(BaseModel):
    id: int
    title: str
    company_name: str | None = None
    location: str | None = None
    url: str | None = None
    final_score: float
    verdict: str


class RecommendationsResponse(BaseModel):
    profile_id: int
    items: list[RecommendationItem]


class RecomputeTaskResponse(BaseModel):
    task_id: str


class EvidenceItem(BaseModel):
    evidence_text: str
    confidence: float
    evidence_type: str


class TailoringResponse(BaseModel):
    profile_id: int
    vacancy_id: int
    explanation: dict[str, Any]
    evidence: list[EvidenceItem]
