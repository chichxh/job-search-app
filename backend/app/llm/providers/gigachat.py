from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

from app.core.config import get_llm_settings
from app.llm.base import (
    LLMAuthError,
    LLMClient,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMUpstreamError,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _TokenState:
    token: str
    expires_at: datetime


class GigaChatClient(LLMClient):
    provider = "gigachat"

    def __init__(self) -> None:
        self._settings = get_llm_settings()
        if not self._settings.gigachat_auth_key:
            raise LLMAuthError(
                "GIGACHAT_AUTH_KEY is not configured. "
                "Set Basic auth key from GigaChat cabinet in environment."
            )

        self._http = httpx.Client(verify=self._settings.gigachat_verify_ssl)
        self._token_lock = threading.Lock()
        self._token_state: _TokenState | None = None

    def _token_valid(self) -> bool:
        if self._token_state is None:
            return False
        return (self._token_state.expires_at - datetime.now(timezone.utc)).total_seconds() > 120

    def _parse_expiry(self, payload: dict) -> datetime:
        now = datetime.now(timezone.utc)

        if payload.get("expires_at"):
            raw_expires_at = payload["expires_at"]

            if isinstance(raw_expires_at, (int, float)):
                timestamp = float(raw_expires_at)
                if timestamp > 1e12:
                    timestamp /= 1000
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)

            if isinstance(raw_expires_at, str):
                normalized = raw_expires_at.strip()

                if normalized.isdigit():
                    timestamp = float(normalized)
                    if timestamp > 1e12:
                        timestamp /= 1000
                    return datetime.fromtimestamp(timestamp, tz=timezone.utc)

                if normalized.endswith("Z"):
                    normalized = normalized.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized).astimezone(timezone.utc)

        ttl_seconds = payload.get("expires_in") or payload.get("ttl")
        if ttl_seconds is not None:
            return now + timedelta(seconds=int(ttl_seconds))

        return now + timedelta(minutes=30)

    def ensure_token(self) -> str:
        if self._token_valid():
            return self._token_state.token

        with self._token_lock:
            if self._token_valid():
                return self._token_state.token

            headers = {
                "Authorization": f"Basic {self._settings.gigachat_auth_key}",
                "RqUID": str(uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            body = {"scope": self._settings.gigachat_scope}

            try:
                response = self._http.post(
                    self._settings.gigachat_oauth_url,
                    headers=headers,
                    data=body,
                    timeout=20.0,
                )
            except httpx.HTTPError as exc:
                raise LLMUpstreamError("Failed to reach GigaChat OAuth endpoint") from exc

            if response.status_code in {401, 403}:
                raise LLMAuthError("GigaChat OAuth authentication failed")
            if response.status_code >= 400:
                raise LLMUpstreamError(
                    f"GigaChat OAuth request failed with status {response.status_code}"
                )

            payload = response.json()
            access_token = payload.get("access_token")
            if not access_token:
                raise LLMAuthError("GigaChat OAuth response does not contain access_token")

            self._token_state = _TokenState(
                token=access_token,
                expires_at=self._parse_expiry(payload),
            )

            logger.info(
                "llm_token_refreshed provider=%s status=%s",
                self.provider,
                response.status_code,
            )

            return self._token_state.token

    def generate(self, req: LLMRequest) -> LLMResponse:
        token = self.ensure_token()
        model = req.model or self._settings.model
        endpoint = f"{self._settings.gigachat_api_base.rstrip('/')}/api/v1/chat/completions"

        payload = {
            "model": model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in req.messages],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        attempts = 3
        backoff_seconds = 1.0
        timeout = req.timeout_s or 60.0
        response: httpx.Response | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = self._http.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
            except httpx.HTTPError as exc:
                if attempt == attempts:
                    raise LLMUpstreamError("Failed to reach GigaChat API") from exc
                time.sleep(backoff_seconds)
                backoff_seconds *= 2
                continue

            status = response.status_code
            logger.info(
                "llm_generate provider=%s model=%s status=%s",
                self.provider,
                model,
                status,
            )

            if status in {401, 403}:
                if attempt == 1:
                    with self._token_lock:
                        self._token_state = None
                    token = self.ensure_token()
                    headers["Authorization"] = f"Bearer {token}"
                    continue
                raise LLMAuthError(f"GigaChat request unauthorized (status={status})")

            if status == 429:
                raise LLMRateLimitError("GigaChat rate limit exceeded")

            if status >= 500:
                if attempt == attempts:
                    raise LLMUpstreamError(
                        f"GigaChat upstream error after retries (status={status})"
                    )
                time.sleep(backoff_seconds)
                backoff_seconds *= 2
                continue

            if status >= 400:
                raise LLMUpstreamError(f"GigaChat request failed (status={status})")

            data = response.json()
            choices = data.get("choices") or []
            text = ""
            if choices:
                message = choices[0].get("message") or {}
                text = message.get("content", "")

            return LLMResponse(
                text=text,
                provider=self.provider,
                model=(data.get("model") or model),
                usage=data.get("usage"),
                raw=data,
            )

        raise LLMUpstreamError("GigaChat request failed unexpectedly")
