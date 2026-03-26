from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Profile, User


OWNERSHIP_DENIAL_DETAIL = "Resource not found"


def get_owned_profile(db: Session, *, profile_id: int, current_user: User) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None or profile.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=OWNERSHIP_DENIAL_DETAIL)
    return profile


def get_owned_profile_resource(
    db: Session,
    *,
    model: Any,
    resource_id: int,
    profile_id: int,
    detail: str,
):
    resource = db.get(model, resource_id)
    if resource is None or resource.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return resource
