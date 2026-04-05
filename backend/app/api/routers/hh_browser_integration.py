from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import HHBrowserConnection, User
from app.db.session import get_db
from app.schemas.hh_browser_integration import (
    HHBrowserConnectInitRequest,
    HHBrowserConnectionSummary,
    HHBrowserMarkAwaitingCodeRequest,
    HHBrowserMarkConnectedRequest,
    HHBrowserMarkFailedRequest,
)
from app.utils.log_safety import redact_text

router = APIRouter(prefix="/integrations/hh-browser", tags=["hh-browser"], dependencies=[Depends(get_current_user)])

ALLOWED_STATUSES = {
    "disconnected",
    "connecting",
    "awaiting_code",
    "connected",
    "requires_reauth",
    "failed",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_user_connection(db: Session, *, user_id: int) -> HHBrowserConnection:
    connection = next((item for item in db.query(HHBrowserConnection).all() if item.user_id == user_id), None)
    if connection is None:
        connection = HHBrowserConnection(user_id=user_id, status="disconnected", requires_reauth=False)
        db.add(connection)
        db.commit()
        db.refresh(connection)
    return connection


def _to_summary(connection: HHBrowserConnection) -> HHBrowserConnectionSummary:
    payload = {
        "status": connection.status,
        "requires_reauth": bool(connection.requires_reauth),
        "last_authenticated_at": connection.last_authenticated_at,
        "last_checked_at": connection.last_checked_at,
        "session_present": bool(connection.session_state_ref),
        "last_error_code": connection.last_error_code,
        "last_error_message": connection.last_error_message,
        "updated_at": connection.updated_at,
    }
    try:
        return HHBrowserConnectionSummary.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid HH browser state") from exc


def _apply_status(connection: HHBrowserConnection, *, status_value: str) -> None:
    if status_value not in ALLOWED_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported status")
    connection.status = status_value
    connection.updated_at = _now_utc()


@router.get("/status", response_model=HHBrowserConnectionSummary)
def hh_browser_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HHBrowserConnectionSummary:
    connection = _ensure_user_connection(db, user_id=current_user.id)
    return _to_summary(connection)


@router.post("/connect/init", response_model=HHBrowserConnectionSummary)
def hh_browser_connect_init(
    payload: HHBrowserConnectInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HHBrowserConnectionSummary:
    connection = _ensure_user_connection(db, user_id=current_user.id)
    _apply_status(connection, status_value="connecting")
    connection.requires_reauth = False
    connection.last_checked_at = _now_utc()
    if payload.session_state_ref:
        connection.session_state_ref = payload.session_state_ref
        connection.session_expires_at = payload.session_expires_at
    connection.last_error_code = None
    connection.last_error_message = None
    db.commit()
    db.refresh(connection)
    return _to_summary(connection)


@router.post("/mark-awaiting-code", response_model=HHBrowserConnectionSummary)
def hh_browser_mark_awaiting_code(
    payload: HHBrowserMarkAwaitingCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HHBrowserConnectionSummary:
    connection = _ensure_user_connection(db, user_id=current_user.id)
    _apply_status(connection, status_value="awaiting_code")
    connection.requires_reauth = bool(payload.requires_reauth)
    connection.last_checked_at = _now_utc()
    db.commit()
    db.refresh(connection)
    return _to_summary(connection)


@router.post("/mark-connected", response_model=HHBrowserConnectionSummary)
def hh_browser_mark_connected(
    payload: HHBrowserMarkConnectedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HHBrowserConnectionSummary:
    connection = _ensure_user_connection(db, user_id=current_user.id)
    _apply_status(connection, status_value="connected")
    connection.requires_reauth = False
    connection.last_authenticated_at = _now_utc()
    connection.last_checked_at = connection.last_authenticated_at
    if payload.session_state_ref:
        connection.session_state_ref = payload.session_state_ref
    if payload.session_expires_at is not None:
        connection.session_expires_at = payload.session_expires_at
    connection.last_error_code = None
    connection.last_error_message = None
    db.commit()
    db.refresh(connection)
    return _to_summary(connection)


@router.post("/mark-failed", response_model=HHBrowserConnectionSummary)
def hh_browser_mark_failed(
    payload: HHBrowserMarkFailedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HHBrowserConnectionSummary:
    connection = _ensure_user_connection(db, user_id=current_user.id)
    _apply_status(connection, status_value="failed")
    connection.requires_reauth = bool(payload.requires_reauth)
    connection.last_checked_at = _now_utc()
    connection.last_error_code = payload.error_code
    connection.last_error_message = redact_text(payload.error_message, max_len=160)
    db.commit()
    db.refresh(connection)
    return _to_summary(connection)


@router.post("/disconnect", response_model=HHBrowserConnectionSummary)
def hh_browser_disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HHBrowserConnectionSummary:
    connection = _ensure_user_connection(db, user_id=current_user.id)
    _apply_status(connection, status_value="disconnected")
    connection.requires_reauth = False
    connection.last_checked_at = _now_utc()
    connection.session_state_ref = None
    connection.session_expires_at = None
    connection.last_error_code = None
    connection.last_error_message = None
    db.commit()
    db.refresh(connection)
    return _to_summary(connection)
