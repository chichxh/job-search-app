from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    CoverLetterVersion,
    Profile,
    ProfileAchievement,
    ProfileCertificate,
    ProfileEducation,
    ProfileExperience,
    ProfileLanguage,
    ProfileLink,
    ProfileProject,
    ProfileSkill,
    ResumeVersion,
)
from app.db.session import get_db
from app.schemas.cover_letter_version import (
    CoverLetterVersionCreate,
    CoverLetterVersionRead,
    CoverLetterVersionUpdate,
)
from app.schemas.profile_achievement import ProfileAchievementCreate, ProfileAchievementRead, ProfileAchievementUpdate
from app.schemas.profile_certificate import ProfileCertificateCreate, ProfileCertificateRead, ProfileCertificateUpdate
from app.schemas.profile_education import ProfileEducationCreate, ProfileEducationRead, ProfileEducationUpdate
from app.schemas.profile_experience import ProfileExperienceCreate, ProfileExperienceRead, ProfileExperienceUpdate
from app.schemas.profile_language import ProfileLanguageCreate, ProfileLanguageRead, ProfileLanguageUpdate
from app.schemas.profile_link import ProfileLinkCreate, ProfileLinkRead, ProfileLinkUpdate
from app.schemas.profile_project import ProfileProjectCreate, ProfileProjectRead, ProfileProjectUpdate
from app.schemas.profile_skill import ProfileSkillCreate, ProfileSkillRead, ProfileSkillUpdate
from app.schemas.resume_version import ResumeVersionCreate, ResumeVersionRead, ResumeVersionUpdate

router = APIRouter(prefix="/profiles", tags=["profile-data"])


def _ensure_profile(db: Session, profile_id: int) -> None:
    if db.get(Profile, profile_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")


def _get_owned_or_404(db: Session, model: Any, profile_id: int, item_id: int, detail: str):
    item = db.get(model, item_id)
    if item is None or item.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return item


@router.get("/{profile_id}/experiences", response_model=list[ProfileExperienceRead])
def list_experiences(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return db.query(ProfileExperience).filter(ProfileExperience.profile_id == profile_id).order_by(ProfileExperience.id.desc()).all()


@router.post("/{profile_id}/experiences", response_model=ProfileExperienceRead, status_code=status.HTTP_201_CREATED)
def create_experience(profile_id: int, payload: ProfileExperienceCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ProfileExperience(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/experiences/{item_id}", response_model=ProfileExperienceRead)
def update_experience(profile_id: int, item_id: int, payload: ProfileExperienceUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileExperience, profile_id, item_id, "Experience not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{profile_id}/experiences/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileExperience, profile_id, item_id, "Experience not found")
    db.delete(item)
    db.commit()


@router.get("/{profile_id}/projects", response_model=list[ProfileProjectRead])
def list_projects(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return db.query(ProfileProject).filter(ProfileProject.profile_id == profile_id).order_by(ProfileProject.id.desc()).all()


@router.post("/{profile_id}/projects", response_model=ProfileProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(profile_id: int, payload: ProfileProjectCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ProfileProject(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/projects/{item_id}", response_model=ProfileProjectRead)
def update_project(profile_id: int, item_id: int, payload: ProfileProjectUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileProject, profile_id, item_id, "Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{profile_id}/projects/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileProject, profile_id, item_id, "Project not found")
    db.delete(item)
    db.commit()


@router.get("/{profile_id}/achievements", response_model=list[ProfileAchievementRead])
def list_achievements(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return db.query(ProfileAchievement).filter(ProfileAchievement.profile_id == profile_id).order_by(ProfileAchievement.id.desc()).all()


@router.post("/{profile_id}/achievements", response_model=ProfileAchievementRead, status_code=status.HTTP_201_CREATED)
def create_achievement(profile_id: int, payload: ProfileAchievementCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ProfileAchievement(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/achievements/{item_id}", response_model=ProfileAchievementRead)
def update_achievement(profile_id: int, item_id: int, payload: ProfileAchievementUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileAchievement, profile_id, item_id, "Achievement not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{profile_id}/achievements/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_achievement(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileAchievement, profile_id, item_id, "Achievement not found")
    db.delete(item)
    db.commit()


@router.get("/{profile_id}/education", response_model=list[ProfileEducationRead])
def list_education(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return db.query(ProfileEducation).filter(ProfileEducation.profile_id == profile_id).order_by(ProfileEducation.id.desc()).all()


@router.post("/{profile_id}/education", response_model=ProfileEducationRead, status_code=status.HTTP_201_CREATED)
def create_education(profile_id: int, payload: ProfileEducationCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ProfileEducation(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/education/{item_id}", response_model=ProfileEducationRead)
def update_education(profile_id: int, item_id: int, payload: ProfileEducationUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileEducation, profile_id, item_id, "Education not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{profile_id}/education/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileEducation, profile_id, item_id, "Education not found")
    db.delete(item)
    db.commit()


@router.get("/{profile_id}/certificates", response_model=list[ProfileCertificateRead])
def list_certificates(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return (
        db.query(ProfileCertificate).filter(ProfileCertificate.profile_id == profile_id).order_by(ProfileCertificate.id.desc()).all()
    )


@router.post("/{profile_id}/certificates", response_model=ProfileCertificateRead, status_code=status.HTTP_201_CREATED)
def create_certificate(profile_id: int, payload: ProfileCertificateCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ProfileCertificate(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/certificates/{item_id}", response_model=ProfileCertificateRead)
def update_certificate(profile_id: int, item_id: int, payload: ProfileCertificateUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileCertificate, profile_id, item_id, "Certificate not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{profile_id}/certificates/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certificate(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileCertificate, profile_id, item_id, "Certificate not found")
    db.delete(item)
    db.commit()


@router.get("/{profile_id}/skills", response_model=list[ProfileSkillRead])
def list_skills(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return db.query(ProfileSkill).filter(ProfileSkill.profile_id == profile_id).order_by(ProfileSkill.id.desc()).all()


@router.post("/{profile_id}/skills", response_model=ProfileSkillRead, status_code=status.HTTP_201_CREATED)
def create_skill(profile_id: int, payload: ProfileSkillCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ProfileSkill(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/skills/{item_id}", response_model=ProfileSkillRead)
def update_skill(profile_id: int, item_id: int, payload: ProfileSkillUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileSkill, profile_id, item_id, "Skill not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{profile_id}/skills/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileSkill, profile_id, item_id, "Skill not found")
    db.delete(item)
    db.commit()


@router.get("/{profile_id}/languages", response_model=list[ProfileLanguageRead])
def list_languages(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return db.query(ProfileLanguage).filter(ProfileLanguage.profile_id == profile_id).order_by(ProfileLanguage.id.desc()).all()


@router.post("/{profile_id}/languages", response_model=ProfileLanguageRead, status_code=status.HTTP_201_CREATED)
def create_language(profile_id: int, payload: ProfileLanguageCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ProfileLanguage(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/languages/{item_id}", response_model=ProfileLanguageRead)
def update_language(profile_id: int, item_id: int, payload: ProfileLanguageUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileLanguage, profile_id, item_id, "Language not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{profile_id}/languages/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_language(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileLanguage, profile_id, item_id, "Language not found")
    db.delete(item)
    db.commit()


@router.get("/{profile_id}/links", response_model=list[ProfileLinkRead])
def list_links(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return db.query(ProfileLink).filter(ProfileLink.profile_id == profile_id).order_by(ProfileLink.id.desc()).all()


@router.post("/{profile_id}/links", response_model=ProfileLinkRead, status_code=status.HTTP_201_CREATED)
def create_link(profile_id: int, payload: ProfileLinkCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ProfileLink(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/links/{item_id}", response_model=ProfileLinkRead)
def update_link(profile_id: int, item_id: int, payload: ProfileLinkUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileLink, profile_id, item_id, "Link not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{profile_id}/links/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ProfileLink, profile_id, item_id, "Link not found")
    db.delete(item)
    db.commit()


@router.get("/{profile_id}/resume-versions", response_model=list[ResumeVersionRead])
def list_resume_versions(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return db.query(ResumeVersion).filter(ResumeVersion.profile_id == profile_id).order_by(ResumeVersion.id.desc()).all()


@router.post("/{profile_id}/resume-versions", response_model=ResumeVersionRead, status_code=status.HTTP_201_CREATED)
def create_resume_version(profile_id: int, payload: ResumeVersionCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = ResumeVersion(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/resume-versions/{item_id}", response_model=ResumeVersionRead)
def update_resume_version(profile_id: int, item_id: int, payload: ResumeVersionUpdate, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ResumeVersion, profile_id, item_id, "Resume version not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{profile_id}/resume-versions/{item_id}/approve", response_model=ResumeVersionRead)
def approve_resume_version(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, ResumeVersion, profile_id, item_id, "Resume version not found")
    item.status = "approved"
    item.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


@router.get("/{profile_id}/cover-letter-versions", response_model=list[CoverLetterVersionRead])
def list_cover_letter_versions(profile_id: int, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    return (
        db.query(CoverLetterVersion)
        .filter(CoverLetterVersion.profile_id == profile_id)
        .order_by(CoverLetterVersion.id.desc())
        .all()
    )


@router.post(
    "/{profile_id}/cover-letter-versions",
    response_model=CoverLetterVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_cover_letter_version(profile_id: int, payload: CoverLetterVersionCreate, db: Session = Depends(get_db)):
    _ensure_profile(db, profile_id)
    item = CoverLetterVersion(profile_id=profile_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{profile_id}/cover-letter-versions/{item_id}", response_model=CoverLetterVersionRead)
def update_cover_letter_version(
    profile_id: int,
    item_id: int,
    payload: CoverLetterVersionUpdate,
    db: Session = Depends(get_db),
):
    item = _get_owned_or_404(db, CoverLetterVersion, profile_id, item_id, "Cover letter version not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{profile_id}/cover-letter-versions/{item_id}/approve", response_model=CoverLetterVersionRead)
def approve_cover_letter_version(profile_id: int, item_id: int, db: Session = Depends(get_db)):
    item = _get_owned_or_404(db, CoverLetterVersion, profile_id, item_id, "Cover letter version not found")
    item.status = "approved"
    item.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item
