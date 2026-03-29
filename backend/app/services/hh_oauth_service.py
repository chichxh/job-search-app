import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import HHOAuthConnection, Profile
from app.services.hh_profile_importer import HHProfileImporter


class HHOAuthError(Exception):
    """Raised for normalized HH OAuth/API errors."""


@dataclass(slots=True)
class HHImportOutcome:
    profile_id: int
    resume_id: str
    imported_at: datetime
    updated_fields: list[str]
    replaced_sections: list[str]


class HHOAuthService:
    AUTHORIZE_URL = "https://hh.ru/oauth/authorize"
    TOKEN_URL = "https://hh.ru/oauth/token"
    API_BASE_URL = "https://api.hh.ru"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.client_id = os.getenv("HH_OAUTH_CLIENT_ID")
        self.client_secret = os.getenv("HH_OAUTH_CLIENT_SECRET")
        self.redirect_uri = os.getenv("HH_OAUTH_REDIRECT_URI")
        self.scopes = os.getenv("HH_OAUTH_SCOPES", "").strip()
        self.user_agent = os.getenv("HH_USER_AGENT")
        self.state_secret = os.getenv("HH_OAUTH_STATE_SECRET") or os.getenv("AUTH_JWT_SECRET", "dev-only-change-me")
        self.profile_importer = HHProfileImporter(db)

        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="HH OAuth is not configured",
            )

    def build_authorize_url(self, *, user_id: int) -> str:
        state = self._encode_state(user_id=user_id)
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "state": state,
            "redirect_uri": self.redirect_uri,
        }
        if self.scopes:
            params["scope"] = self.scopes
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def handle_callback(self, *, code: str, state: str) -> HHOAuthConnection:
        user_id = self._decode_state(state)
        token_payload = await self._exchange_code(code)
        me_payload = await self._fetch_me(token_payload["access_token"])

        connection = self._get_connection_for_user(user_id)
        if connection is None:
            connection = HHOAuthConnection(user_id=user_id, provider="hh")

        now = datetime.now(timezone.utc)
        connection.access_token = token_payload["access_token"]
        connection.refresh_token = token_payload.get("refresh_token")
        connection.scope = token_payload.get("scope")
        connection.token_type = token_payload.get("token_type")
        expires_in = int(token_payload.get("expires_in") or 0)
        connection.token_expires_at = now + timedelta(seconds=expires_in) if expires_in > 0 else None
        connection.connected_at = now
        connection.updated_at = now
        connection.hh_user_id = str(me_payload.get("id") or "") or None
        connection.hh_email = me_payload.get("email")

        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    async def disconnect(self, *, user_id: int) -> None:
        connection = self._get_connection_for_user(user_id)
        if connection is None:
            return
        self.db.delete(connection)
        self.db.commit()

    def get_connection_status(self, *, user_id: int) -> HHOAuthConnection | None:
        return self._get_connection_for_user(user_id)

    async def list_resumes(self, *, user_id: int) -> list[dict[str, Any]]:
        token = await self._get_valid_access_token(user_id)
        payload = await self._hh_get("/resumes/mine", token)
        return payload.get("items") or []

    async def import_profile(self, *, user_id: int, profile: Profile, resume_id: Optional[str]) -> HHImportOutcome:
        token = await self._get_valid_access_token(user_id)
        target_resume_id = resume_id
        if not target_resume_id:
            resumes = await self.list_resumes(user_id=user_id)
            if not resumes:
                raise HHOAuthError("No HH resumes found for current user")
            target_resume_id = str(resumes[0].get("id"))

        resume_payload = await self._hh_get(f"/resumes/{target_resume_id}", token)

        updated_fields, replaced_sections = self.profile_importer.import_resume(profile=profile, resume=resume_payload)

        profile.resume_text = profile.resume_text or "Imported from HH"
        imported_at = datetime.now(timezone.utc)

        connection = self._get_connection_for_user(user_id)
        if connection:
            connection.hh_resume_id = target_resume_id
            connection.last_imported_at = imported_at
            self.db.add(connection)

        self.db.add(profile)
        self.db.commit()
        return HHImportOutcome(
            profile_id=profile.id,
            resume_id=target_resume_id,
            imported_at=imported_at,
            updated_fields=updated_fields,
            replaced_sections=replaced_sections,
        )


    def _get_connection_for_user(self, user_id: int) -> HHOAuthConnection | None:
        for connection in self.db.query(HHOAuthConnection).all():
            if connection.user_id == user_id and connection.provider == "hh":
                return connection
        return None

    async def _get_valid_access_token(self, user_id: int) -> str:
        connection = self._get_connection_for_user(user_id)
        if connection is None:
            raise HHOAuthError("HH is not connected")

        now = datetime.now(timezone.utc)
        if connection.token_expires_at and connection.token_expires_at <= now + timedelta(seconds=20):
            if not connection.refresh_token:
                raise HHOAuthError("HH connection expired, reconnect required")
            refreshed = await self._refresh_token(connection.refresh_token)
            connection.access_token = refreshed["access_token"]
            connection.refresh_token = refreshed.get("refresh_token") or connection.refresh_token
            expires_in = int(refreshed.get("expires_in") or 0)
            connection.token_expires_at = now + timedelta(seconds=expires_in) if expires_in > 0 else None
            connection.scope = refreshed.get("scope") or connection.scope
            connection.token_type = refreshed.get("token_type") or connection.token_type
            connection.updated_at = now
            self.db.add(connection)
            self.db.commit()

        return connection.access_token

    async def _exchange_code(self, code: str) -> dict[str, Any]:
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        return await self._token_request(payload)

    async def _refresh_token(self, refresh_token: str) -> dict[str, Any]:
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        return await self._token_request(payload)

    async def _token_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.user_agent:
            headers["User-Agent"] = self.user_agent

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(self.TOKEN_URL, data=payload, headers=headers)

        if response.status_code >= 400:
            raise HHOAuthError("HH OAuth request failed")

        data = response.json()
        if not data.get("access_token"):
            raise HHOAuthError("HH OAuth response is invalid")
        return data

    async def _fetch_me(self, access_token: str) -> dict[str, Any]:
        return await self._hh_get("/me", access_token)

    async def _hh_get(self, path: str, access_token: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if self.user_agent:
            headers["User-Agent"] = self.user_agent

        async with httpx.AsyncClient(base_url=self.API_BASE_URL, timeout=20.0) as client:
            response = await client.get(path, headers=headers)

        if response.status_code >= 400:
            raise HHOAuthError("HH provider request failed")

        return response.json()

    def _encode_state(self, *, user_id: int) -> str:
        payload = {
            "user_id": user_id,
            "nonce": secrets.token_urlsafe(12),
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
        }
        raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_part = base64.urlsafe_b64encode(raw_payload).rstrip(b"=")
        signature = hmac.new(self.state_secret.encode("utf-8"), payload_part, hashlib.sha256).digest()
        signature_part = base64.urlsafe_b64encode(signature).rstrip(b"=")
        return f"{payload_part.decode('utf-8')}.{signature_part.decode('utf-8')}"

    def _decode_state(self, state: str) -> int:
        try:
            payload_part_raw, signature_part_raw = state.split(".", 1)
            payload_part = payload_part_raw.encode("utf-8")
            expected_signature = hmac.new(self.state_secret.encode("utf-8"), payload_part, hashlib.sha256).digest()
            actual_signature = base64.urlsafe_b64decode(signature_part_raw + "=" * (-len(signature_part_raw) % 4))
            if not hmac.compare_digest(expected_signature, actual_signature):
                raise ValueError("bad signature")

            payload_json = base64.urlsafe_b64decode(payload_part_raw + "=" * (-len(payload_part_raw) % 4))
            payload = json.loads(payload_json)
            if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
                raise ValueError("expired")
            return int(payload["user_id"])
        except Exception as exc:  # noqa: BLE001
            raise HHOAuthError("Invalid OAuth state") from exc
