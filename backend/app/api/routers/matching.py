from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Profile, ResumeEvidence, Vacancy, VacancyScore
from app.db.session import get_db
from app.schemas.matching import (
    RecommendationItem,
    RecommendationsResponse,
    RecomputeTaskResponse,
    TailoringResponse,
)
from app.services.matching.matching_service import MatchingService
from app.tasks.matching_tasks import compute_profile_recommendations

router = APIRouter(prefix="/profiles", tags=["matching"])


@router.get("/{profile_id}/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    profile_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    rows = db.execute(
        select(VacancyScore, Vacancy)
        .join(Vacancy, Vacancy.id == VacancyScore.vacancy_id)
        .where(VacancyScore.profile_id == profile_id)
        .order_by(VacancyScore.final_score.desc(), VacancyScore.id.asc())
        .limit(limit)
    ).all()

    items = [
        RecommendationItem(
            id=vacancy.id,
            title=vacancy.title,
            company_name=vacancy.company_name,
            location=vacancy.location,
            url=vacancy.url,
            final_score=score.final_score,
            verdict=score.verdict,
        )
        for score, vacancy in rows
    ]

    return RecommendationsResponse(profile_id=profile_id, items=items)


@router.post("/{profile_id}/recommendations/recompute", response_model=RecomputeTaskResponse)
def recompute_recommendations(
    profile_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    task = compute_profile_recommendations.delay(profile_id, limit)
    return RecomputeTaskResponse(task_id=task.id)


@router.get("/{profile_id}/vacancies/{vacancy_id}/tailoring", response_model=TailoringResponse)
def get_tailoring(
    profile_id: int,
    vacancy_id: int,
    db: Session = Depends(get_db),
):
    service = MatchingService(db)

    score = db.execute(
        select(VacancyScore).where(
            VacancyScore.profile_id == profile_id,
            VacancyScore.vacancy_id == vacancy_id,
        )
    ).scalar_one_or_none()

    if score is None:
        try:
            score = service.compute_for_pair(profile_id=profile_id, vacancy_id=vacancy_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    evidence_rows = db.execute(
        select(
            ResumeEvidence.evidence_text,
            ResumeEvidence.confidence,
            ResumeEvidence.evidence_type,
        )
        .where(
            ResumeEvidence.profile_id == profile_id,
            ResumeEvidence.vacancy_id == vacancy_id,
        )
        .order_by(ResumeEvidence.confidence.desc(), ResumeEvidence.id.asc())
    ).all()

    return TailoringResponse(
        profile_id=profile_id,
        vacancy_id=vacancy_id,
        explanation=score.explanation,
        evidence=[
            {
                "evidence_text": row.evidence_text,
                "confidence": row.confidence,
                "evidence_type": row.evidence_type,
            }
            for row in evidence_rows
        ],
    )
