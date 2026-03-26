from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    ApplicationStatusHistory,
    CoverLetterVersion,
    Profile,
    ResumeVersion,
    Vacancy,
)
from app.db.session import get_db
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationStatusChange,
    ApplicationStatusHistoryRead,
    ApplicationUpdate,
)

router = APIRouter(prefix="/profiles", tags=["applications"])


def _ensure_profile(db: Session, profile_id: int) -> None:
    if db.get(Profile, profile_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")


def _get_application_or_404(db: Session, profile_id: int, application_id: int) -> Application:
    item = db.get(Application, application_id)
    if item is None or item.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return item


def _validate_resume_version(
    db: Session,
    *,
    profile_id: int,
    vacancy_id: int,
    resume_version_id: int | None,
) -> None:
    if resume_version_id is None:
        return
    resume_version = db.get(ResumeVersion, resume_version_id)
    if resume_version is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume version not found")
    if resume_version.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume version belongs to another profile")
    if resume_version.vacancy_id is not None and resume_version.vacancy_id != vacancy_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume version vacancy_id mismatch")


def _validate_cover_letter_version(
    db: Session,
    *,
    profile_id: int,
    vacancy_id: int,
    cover_letter_version_id: int | None,
) -> None:
    if cover_letter_version_id is None:
        return
    cover_letter = db.get(CoverLetterVersion, cover_letter_version_id)
    if cover_letter is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cover letter version not found")
    if cover_letter.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cover letter belongs to another profile")
    if cover_letter.vacancy_id is not None and cover_letter.vacancy_id != vacancy_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cover letter vacancy_id mismatch")


@router.get("/{profile_id}/applications", response_model=list[ApplicationRead])
def list_applications(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return (
        db.query(Application)
        .filter(Application.profile_id == profile_id)
        .order_by(Application.updated_at.desc(), Application.id.desc())
        .all()
    )


@router.post("/{profile_id}/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(profile_id: int, payload: ApplicationCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)

    vacancy = db.get(Vacancy, payload.vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vacancy not found")

    _validate_resume_version(
        db,
        profile_id=profile_id,
        vacancy_id=payload.vacancy_id,
        resume_version_id=payload.resume_version_id,
    )
    _validate_cover_letter_version(
        db,
        profile_id=profile_id,
        vacancy_id=payload.vacancy_id,
        cover_letter_version_id=payload.cover_letter_version_id,
    )

    item = Application(profile_id=profile_id, **payload.model_dump())
    db.add(item)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application for this vacancy already exists for this profile",
        )

    db.refresh(item)

    db.add(
        ApplicationStatusHistory(
            application_id=item.id,
            from_status=None,
            to_status=item.status,
            note=item.note,
        )
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/{profile_id}/applications/{application_id}", response_model=ApplicationRead)
def get_application(profile_id: int, application_id: int, db: Session = Depends(get_db)):
    return _get_application_or_404(db, profile_id, application_id)


@router.put("/{profile_id}/applications/{application_id}", response_model=ApplicationRead)
def update_application(profile_id: int, application_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)):
    item = _get_application_or_404(db, profile_id, application_id)

    updates = payload.model_dump(exclude_unset=True)
    target_resume_version_id = updates.get("resume_version_id", item.resume_version_id)
    target_cover_letter_version_id = updates.get("cover_letter_version_id", item.cover_letter_version_id)

    _validate_resume_version(
        db,
        profile_id=profile_id,
        vacancy_id=item.vacancy_id,
        resume_version_id=target_resume_version_id,
    )
    _validate_cover_letter_version(
        db,
        profile_id=profile_id,
        vacancy_id=item.vacancy_id,
        cover_letter_version_id=target_cover_letter_version_id,
    )

    for field, value in updates.items():
        setattr(item, field, value)

    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{profile_id}/applications/{application_id}/status", response_model=ApplicationRead)
def change_application_status(
    profile_id: int,
    application_id: int,
    payload: ApplicationStatusChange,
    db: Session = Depends(get_db),
):
    item = _get_application_or_404(db, profile_id, application_id)
    from_status = item.status

    item.status = payload.status
    if payload.note is not None:
        item.note = payload.note
    item.updated_at = datetime.now(timezone.utc)

    db.add(
        ApplicationStatusHistory(
            application_id=item.id,
            from_status=from_status,
            to_status=payload.status,
            note=payload.note,
        )
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/{profile_id}/applications/{application_id}/history", response_model=list[ApplicationStatusHistoryRead])
def list_application_history(profile_id: int, application_id: int, db: Session = Depends(get_db)):
    _get_application_or_404(db, profile_id, application_id)
    return (
        db.query(ApplicationStatusHistory)
        .filter(ApplicationStatusHistory.application_id == application_id)
        .order_by(ApplicationStatusHistory.created_at.desc(), ApplicationStatusHistory.id.desc())
        .all()
    )


@router.delete("/{profile_id}/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(profile_id: int, application_id: int, db: Session = Depends(get_db)):
    item = _get_application_or_404(db, profile_id, application_id)
    db.delete(item)
    db.commit()
