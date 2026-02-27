from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cover_letter_version import CoverLetterVersionRead
from app.schemas.resume_version import ResumeVersionRead
from app.services.docgen.document_generation_service import DocumentGenerationService

router = APIRouter(prefix="/profiles", tags=["docgen"])


@router.post(
    "/{profile_id}/vacancies/{vacancy_id}/resume/generate",
    response_model=ResumeVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_resume_draft(profile_id: int, vacancy_id: int, db: Session = Depends(get_db)):
    service = DocumentGenerationService(db)
    try:
        return service.generate_resume_draft(profile_id=profile_id, vacancy_id=vacancy_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{profile_id}/vacancies/{vacancy_id}/cover-letter/generate",
    response_model=CoverLetterVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_cover_letter_draft(profile_id: int, vacancy_id: int, db: Session = Depends(get_db)):
    service = DocumentGenerationService(db)
    try:
        return service.generate_cover_letter_draft(profile_id=profile_id, vacancy_id=vacancy_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
