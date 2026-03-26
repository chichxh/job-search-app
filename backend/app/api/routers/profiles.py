from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.ownership import get_owned_profile
from app.db.models import Profile, User
from app.db.session import get_db
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.tasks.embedding_tasks import build_profile_embedding

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
