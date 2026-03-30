from dataclasses import asdict
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.ownership import get_owned_profile
from app.db.models import Profile, User
from app.db.session import get_db
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.schemas.resume_import import ResumeExtractionResponse
from app.tasks.embedding_tasks import build_profile_embedding
from app.services.resume_extraction_service import (
    EmptyResumeFileError,
    ResumeExtractionFailedError,
    ResumeExtractionService,
    ResumeFileTooLargeError,
    ResumeNoTextExtractedError,
    UnsupportedResumeFileTypeError,
)

router = APIRouter(prefix="/profiles", tags=["profiles"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = Profile(user_id=current_user.id, **payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    build_profile_embedding.delay(profile.id)
    return profile


@router.get("", response_model=List[ProfileRead])
def list_profiles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [item for item in db.query(Profile).order_by(Profile.id.desc()).all() if item.user_id == current_user.id]


@router.get("/{profile_id}", response_model=ProfileRead)
def get_profile_by_id(profile_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_owned_profile(db, profile_id=profile_id, current_user=current_user)


@router.put("/{profile_id}", response_model=ProfileRead)
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = get_owned_profile(db, profile_id=profile_id, current_user=current_user)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    build_profile_embedding.delay(profile.id)
    return profile


@router.post("/{profile_id}/resume-import/extract", response_model=ResumeExtractionResponse)
async def extract_resume_text(
    profile_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_profile(db, profile_id=profile_id, current_user=current_user)

    content = await file.read()
    service = ResumeExtractionService()

    try:
        result = service.extract(filename=file.filename or "resume", content_type=file.content_type, content=content)
    except UnsupportedResumeFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except EmptyResumeFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ResumeFileTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except ResumeNoTextExtractedError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ResumeExtractionFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not result.import_ready:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Extracted resume text is too short")

    return ResumeExtractionResponse(**asdict(result))
