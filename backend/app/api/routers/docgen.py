from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.ownership import get_owned_profile
from app.db.models import User
from app.db.session import get_db
from app.schemas.cover_letter_version import CoverLetterVersionRead
from app.schemas.resume_version import ResumeVersionRead
from app.services.docgen.document_generation_service import (
    DocgenInvalidResultError,
    DocgenMisconfigurationError,
    DocgenNotFoundError,
    DocgenPrerequisiteError,
    DocgenProviderUnavailableError,
    DocumentGenerationService,
)

router = APIRouter(prefix="/profiles", tags=["docgen"], dependencies=[Depends(get_current_user)])


def _map_docgen_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DocgenNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.user_message)
    if isinstance(exc, DocgenPrerequisiteError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.user_message)
    if isinstance(exc, DocgenInvalidResultError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.user_message)
    if isinstance(exc, DocgenProviderUnavailableError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.user_message)
    if isinstance(exc, DocgenMisconfigurationError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.user_message)

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Document generation failed due to internal error.",
    )


@router.post(
    "/{profile_id}/vacancies/{vacancy_id}/resume/generate",
    response_model=ResumeVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_resume_draft(
    profile_id: int,
    vacancy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_profile(db, profile_id=profile_id, current_user=current_user)
    service = DocumentGenerationService(db)
    try:
        return service.generate_resume_draft(profile_id=profile_id, vacancy_id=vacancy_id)
    except Exception as exc:
        raise _map_docgen_error(exc) from exc


@router.post(
    "/{profile_id}/vacancies/{vacancy_id}/cover-letter/generate",
    response_model=CoverLetterVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_cover_letter_draft(
    profile_id: int,
    vacancy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_profile(db, profile_id=profile_id, current_user=current_user)
    service = DocumentGenerationService(db)
    try:
        return service.generate_cover_letter_draft(profile_id=profile_id, vacancy_id=vacancy_id)
    except Exception as exc:
        raise _map_docgen_error(exc) from exc
