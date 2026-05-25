from datetime import datetime, timezone
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_profile, get_current_user
from app.db.models import Profile, User
from app.db.session import get_db
from app.schemas.hh_integration import (
    HHOAuthConnectionStatus,
    HHOAuthStartResponse,
    HHDemoConnectResponse,
    HHDemoProfileSummary,
    HHProfileImportJSONRequest,
    HHProfileImportRequest,
    HHProfileImportResponse,
    HHResumeOption,
)
from app.services.hh_oauth_service import HHOAuthError, HHOAuthService
from app.services.hh_profile_importer import HHImportPayloadError, HHProfileImporter

router = APIRouter(prefix="/integrations/hh", tags=["hh-integration"])
_DEMO_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "hh" / "demo_hh_profile.json"


def _is_hh_demo_enabled() -> bool:
    enabled = (os.getenv("DEMO_MODE", "") or os.getenv("HH_DEMO_MODE", "")).strip().lower()
    return enabled in {"1", "true", "yes", "on"}


@router.post("/connect/start", response_model=HHOAuthStartResponse)
def start_hh_connect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HHOAuthStartResponse:
    service = HHOAuthService(db)
    return HHOAuthStartResponse(authorize_url=service.build_authorize_url(user_id=current_user.id))


@router.get("/callback")
async def hh_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    ok_url = os.getenv("HH_OAUTH_FRONTEND_SUCCESS_URL", "http://localhost:5173/settings?hh=connected")
    fail_url = os.getenv("HH_OAUTH_FRONTEND_ERROR_URL", "http://localhost:5173/settings?hh=connect_failed")

    if error:
        return RedirectResponse(url=f"{fail_url}&reason=provider_error", status_code=status.HTTP_302_FOUND)

    if not code or not state:
        return RedirectResponse(url=f"{fail_url}&reason=missing_params", status_code=status.HTTP_302_FOUND)

    service = HHOAuthService(db)
    try:
        await service.handle_callback(code=code, state=state)
    except HHOAuthError:
        return RedirectResponse(url=f"{fail_url}&reason=oauth_failed", status_code=status.HTTP_302_FOUND)

    return RedirectResponse(url=ok_url, status_code=status.HTTP_302_FOUND)


@router.get("/status", response_model=HHOAuthConnectionStatus)
def hh_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> HHOAuthConnectionStatus:
    service = HHOAuthService(db)
    connection = service.get_connection_status(user_id=current_user.id)
    if not connection:
        return HHOAuthConnectionStatus(connected=False)

    return HHOAuthConnectionStatus(
        connected=True,
        connected_at=connection.connected_at,
        token_expires_at=connection.token_expires_at,
        hh_user_id=connection.hh_user_id,
        hh_resume_id=connection.hh_resume_id,
        last_imported_at=connection.last_imported_at,
    )


@router.get("/resumes", response_model=list[HHResumeOption])
async def list_hh_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[HHResumeOption]:
    service = HHOAuthService(db)
    try:
        resumes = await service.list_resumes(user_id=current_user.id)
    except HHOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    options: list[HHResumeOption] = []
    for resume in resumes:
        options.append(
            HHResumeOption(
                id=str(resume.get("id")),
                title=(resume.get("title") or "HH Resume").strip(),
                updated_at=resume.get("updated_at"),
            )
        )
    return options


@router.post("/import", response_model=HHProfileImportResponse)
async def import_hh_profile(
    payload: HHProfileImportRequest,
    current_user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> HHProfileImportResponse:
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit consent is required to import HH profile data",
        )

    if profile.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    service = HHOAuthService(db)
    try:
        outcome = await service.import_profile(
            user_id=current_user.id,
            profile=profile,
            resume_id=payload.resume_id,
        )
    except HHOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return HHProfileImportResponse(
        profile_id=outcome.profile_id,
        resume_id=outcome.resume_id,
        imported_at=outcome.imported_at.astimezone(timezone.utc),
        updated_fields=outcome.updated_fields,
        replaced_sections=outcome.replaced_sections,
    )


@router.post("/import-json", response_model=HHProfileImportResponse)
async def import_hh_profile_json(
    body: HHProfileImportJSONRequest,
    current_user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> HHProfileImportResponse:
    if not body.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit consent is required to import HH profile data",
        )

    if profile.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    importer = HHProfileImporter(db)
    try:
        selected = importer.select_resume_from_payload(payload=body.payload, resume_id=body.resume_id)
    except HHImportPayloadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    updated_fields, replaced_sections = importer.import_resume(profile=profile, resume=selected.resume_payload)
    profile.resume_text = profile.resume_text or "Imported from HH"
    imported_at = datetime.now(timezone.utc)
    db.add(profile)
    db.commit()

    return HHProfileImportResponse(
        profile_id=profile.id,
        resume_id=selected.resume_id,
        imported_at=imported_at,
        updated_fields=updated_fields,
        replaced_sections=replaced_sections,
    )


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_hh(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    service = HHOAuthService(db)
    await service.disconnect(user_id=current_user.id)


@router.post("/demo-connect", response_model=HHDemoConnectResponse)
async def hh_demo_connect(
    current_user: User = Depends(get_current_user),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> HHDemoConnectResponse:
    if not _is_hh_demo_enabled():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo HH connection is disabled")

    if profile.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    fixture_payload = json.loads(_DEMO_FIXTURE_PATH.read_text(encoding="utf-8"))
    importer = HHProfileImporter(db)
    selected = importer.select_resume_from_payload(payload=fixture_payload, resume_id=None)
    importer.import_resume(profile=profile, resume=selected.resume_payload)
    profile.resume_text = profile.resume_text or "Imported from HH demo profile"
    db.add(profile)
    db.commit()

    raw_skills = selected.resume_payload.get("skill_set")
    skills_count = len(raw_skills) if isinstance(raw_skills, list) else 0
    raw_experiences = selected.resume_payload.get("experience")
    experiences_count = len(raw_experiences) if isinstance(raw_experiences, list) else 0

    return HHDemoConnectResponse(
        status="connected",
        mode="demo",
        profile=HHDemoProfileSummary(
            full_name=profile.full_name or "Тестовый пользователь",
            title=profile.title or "Backend Developer",
            city=profile.city or "Москва",
            skills_count=skills_count,
            experiences_count=experiences_count,
        ),
    )
