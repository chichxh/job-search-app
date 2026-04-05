from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.hh_browser_integration import (
    HHBrowserConnectStartRequest,
    HHBrowserConnectionSummary,
    HHBrowserSessionValidationResponse,
    HHBrowserSubmitCodeRequest,
    HHBrowserSubmitIdentifierRequest,
    HHBrowserSubmitPasswordRequest,
)
from app.services.hh_browser_connect_service import HHBrowserConnectService, InMemoryRuntimeRegistry, LocalSessionStorage
from app.services.hh_browser_playwright import PlaywrightAdapterFactory, PlaywrightSessionProbeFactory

router = APIRouter(prefix="/integrations/hh-browser", tags=["hh-browser"], dependencies=[Depends(get_current_user)])

_runtime_registry = InMemoryRuntimeRegistry(timeout_seconds=600)
_session_storage = LocalSessionStorage()
_adapter_factory = PlaywrightAdapterFactory()
_probe_factory = PlaywrightSessionProbeFactory()


def get_hh_connect_service(db: Session = Depends(get_db)) -> HHBrowserConnectService:
    return HHBrowserConnectService(
        db,
        adapter_factory=_adapter_factory,
        runtime_registry=_runtime_registry,
        session_storage=_session_storage,
        session_probe_factory=_probe_factory,
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
