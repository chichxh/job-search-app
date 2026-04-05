from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.hh_browser_integration import (
    HHCreateTargetedResumeRequest,
    HHCreateTargetedResumeResponse,
    HHBrowserConnectStartRequest,
    HHBrowserConnectionSummary,
    HHManagedResumeRead,
    HHBrowserSessionValidationResponse,
    HHBrowserSubmitCodeRequest,
    HHBrowserSubmitIdentifierRequest,
    HHBrowserSubmitPasswordRequest,
    HHManagedResumeVisibilityRead,
)
from app.services.hh_browser_connect_service import HHBrowserConnectService, InMemoryRuntimeRegistry, LocalSessionStorage
from app.services.hh_resume_visibility_service import HHResumeVisibilityAutomationClientStub, HHResumeVisibilityService
from app.services.hh_targeted_resume_service import HHCreateTargetedResumeService, HHTargetedPayloadBuilder
from app.services.hh_targeted_resume_automation import PlaywrightTargetedResumeAutomationClient
from app.services.hh_browser_playwright import PlaywrightAdapterFactory, PlaywrightSessionProbeFactory

router = APIRouter(prefix="/integrations/hh-browser", tags=["hh-browser"], dependencies=[Depends(get_current_user)])

_runtime_registry = InMemoryRuntimeRegistry(timeout_seconds=600)
_session_storage = LocalSessionStorage()
_adapter_factory = PlaywrightAdapterFactory()
_probe_factory = PlaywrightSessionProbeFactory()
_resume_automation_client = PlaywrightTargetedResumeAutomationClient()
_resume_visibility_automation_client = HHResumeVisibilityAutomationClientStub()


def get_hh_connect_service(db: Session = Depends(get_db)) -> HHBrowserConnectService:
    return HHBrowserConnectService(
        db,
        adapter_factory=_adapter_factory,
        runtime_registry=_runtime_registry,
        session_storage=_session_storage,
        session_probe_factory=_probe_factory,
    )

def get_hh_targeted_resume_service(db: Session = Depends(get_db)) -> HHCreateTargetedResumeService:
    return HHCreateTargetedResumeService(
        db,
        payload_builder=HHTargetedPayloadBuilder(db),
        automation_client=_resume_automation_client,
    )


def get_hh_resume_visibility_service(db: Session = Depends(get_db)) -> HHResumeVisibilityService:
    return HHResumeVisibilityService(
        db,
        automation_client=_resume_visibility_automation_client,
    )


@router.post("/connect/start", response_model=HHBrowserConnectionSummary)
def hh_browser_connect_start(
    payload: HHBrowserConnectStartRequest,
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.start(user_id=current_user.id, force_restart=payload.force_restart)


@router.get("/connect/state", response_model=HHBrowserConnectionSummary)
def hh_browser_connect_state(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.get_state(user_id=current_user.id)


@router.post("/connect/identifier", response_model=HHBrowserConnectionSummary)
def hh_browser_connect_identifier(
    payload: HHBrowserSubmitIdentifierRequest,
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.submit_identifier(
        user_id=current_user.id,
        identifier=payload.identifier,
        identifier_type=payload.identifier_type,
    )


@router.post("/connect/password", response_model=HHBrowserConnectionSummary)
def hh_browser_connect_password(
    payload: HHBrowserSubmitPasswordRequest,
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.submit_password(user_id=current_user.id, password=payload.password)


@router.post("/connect/code", response_model=HHBrowserConnectionSummary)
def hh_browser_connect_code(
    payload: HHBrowserSubmitCodeRequest,
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.submit_code(user_id=current_user.id, code=payload.code)


@router.post("/connect/cancel", response_model=HHBrowserConnectionSummary)
def hh_browser_connect_cancel(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.cancel(user_id=current_user.id)


@router.post("/session/restore", response_model=HHBrowserConnectionSummary)
def hh_browser_session_restore(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.restore_session(user_id=current_user.id)


@router.post("/session/check", response_model=HHBrowserConnectionSummary)
def hh_browser_session_check(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.check_session(user_id=current_user.id)


@router.post("/session/validate", response_model=HHBrowserSessionValidationResponse)
def hh_browser_session_validate(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserSessionValidationResponse:
    return HHBrowserSessionValidationResponse.model_validate(service.validate_session(user_id=current_user.id))


@router.post("/session/refresh-status", response_model=HHBrowserConnectionSummary)
def hh_browser_session_refresh_status(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.refresh_session_status(user_id=current_user.id)


@router.post("/session/require-reauth", response_model=HHBrowserConnectionSummary)
def hh_browser_session_require_reauth(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.require_reauth(user_id=current_user.id)


# Backward-compatible aliases for foundation endpoints used by existing product wiring.
@router.get("/status", response_model=HHBrowserConnectionSummary)
def hh_browser_status_legacy(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.get_state(user_id=current_user.id)


@router.post("/disconnect", response_model=HHBrowserConnectionSummary)
def hh_browser_disconnect_legacy(
    current_user: User = Depends(get_current_user),
    service: HHBrowserConnectService = Depends(get_hh_connect_service),
) -> HHBrowserConnectionSummary:
    return service.cancel(user_id=current_user.id)


@router.post("/resumes/create-targeted", response_model=HHCreateTargetedResumeResponse, status_code=201)
def create_targeted_resume(
    payload: HHCreateTargetedResumeRequest,
    current_user: User = Depends(get_current_user),
    service: HHCreateTargetedResumeService = Depends(get_hh_targeted_resume_service),
) -> HHCreateTargetedResumeResponse:
    managed_resume, targeted_payload = service.create_targeted_resume(user_id=current_user.id, request=payload)
    return HHCreateTargetedResumeResponse(
        managed_resume=HHManagedResumeRead.model_validate(managed_resume),
        payload_preview=targeted_payload if payload.dry_run else None,
    )


@router.get("/resumes", response_model=list[HHManagedResumeRead])
def list_managed_resumes(
    current_user: User = Depends(get_current_user),
    service: HHCreateTargetedResumeService = Depends(get_hh_targeted_resume_service),
) -> list[HHManagedResumeRead]:
    return [HHManagedResumeRead.model_validate(item) for item in service.list_managed_resumes(user_id=current_user.id)]


@router.get("/resumes/{managed_resume_id}", response_model=HHManagedResumeRead)
def get_managed_resume(
    managed_resume_id: int,
    current_user: User = Depends(get_current_user),
    service: HHCreateTargetedResumeService = Depends(get_hh_targeted_resume_service),
) -> HHManagedResumeRead:
    item = service.get_managed_resume(user_id=current_user.id, managed_resume_id=managed_resume_id)
    return HHManagedResumeRead.model_validate(item)


def _visibility_from_managed(item) -> HHManagedResumeVisibilityRead:
    return HHManagedResumeVisibilityRead(
        managed_resume_id=item.id,
        desired_visibility_mode=item.desired_visibility_mode,
        current_visibility_mode=item.current_visibility_mode,
        visibility_last_checked_at=item.visibility_last_checked_at,
        visibility_last_changed_at=item.visibility_last_changed_at,
        visibility_status=item.visibility_status,
        visibility_error_code=item.visibility_error_code,
        visibility_error_message=item.visibility_error_message,
    )


@router.get("/resumes/{managed_resume_id}/visibility", response_model=HHManagedResumeVisibilityRead)
def get_managed_resume_visibility(
    managed_resume_id: int,
    current_user: User = Depends(get_current_user),
    service: HHResumeVisibilityService = Depends(get_hh_resume_visibility_service),
) -> HHManagedResumeVisibilityRead:
    item = service.get_visibility(user_id=current_user.id, managed_resume_id=managed_resume_id)
    return _visibility_from_managed(item)


@router.post("/resumes/{managed_resume_id}/visibility/check", response_model=HHManagedResumeVisibilityRead)
def check_managed_resume_visibility(
    managed_resume_id: int,
    current_user: User = Depends(get_current_user),
    service: HHResumeVisibilityService = Depends(get_hh_resume_visibility_service),
) -> HHManagedResumeVisibilityRead:
    item = service.check_visibility(user_id=current_user.id, managed_resume_id=managed_resume_id)
    return _visibility_from_managed(item)


@router.post("/resumes/{managed_resume_id}/visibility/hide-from-all", response_model=HHManagedResumeVisibilityRead)
def hide_managed_resume_from_all(
    managed_resume_id: int,
    current_user: User = Depends(get_current_user),
    service: HHResumeVisibilityService = Depends(get_hh_resume_visibility_service),
) -> HHManagedResumeVisibilityRead:
    item = service.hide_from_all(user_id=current_user.id, managed_resume_id=managed_resume_id)
    return _visibility_from_managed(item)
