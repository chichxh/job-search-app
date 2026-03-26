from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_profile, get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import Profile, User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, MeResponse, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _find_user_by_email(db: Session, email: str) -> User | None:
    return next((item for item in db.query(User).all() if item.email == email), None)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = _find_user_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = Profile(user_id=user.id, resume_text="")
    db.add(profile)
    db.commit()

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _find_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    current_profile: Profile = Depends(get_current_profile),
):
    return MeResponse(user=UserRead.model_validate(current_user), profile_id=current_profile.id)
