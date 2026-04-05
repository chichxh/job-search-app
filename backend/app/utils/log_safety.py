from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY_MARKERS = (
    "cover_letter",
    "cookies",
    "cookie",
    "storage_state",
    "session_state",
    "session_storage",
    "session_ref",
    "resume_text",
    "content_text",
    "otp",
    "one_time_code",
    "verification_code",
    "phone",
    "email",
    "token",
    "secret",
    "password",
    "authorization",
    "auth",
    "prompt",
    "raw",
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{8,}\d)")
_SESSION_REF_RE = re.compile(r"local://hh-browser-session/[A-Za-z0-9._-]+")


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS)


def redact_text(value: str, *, max_len: int = 120) -> str:
    """Mask common PII patterns and trim long log values."""
    redacted = _EMAIL_RE.sub("[redacted_email]", value)
    redacted = _PHONE_RE.sub("[redacted_phone]", redacted)
    redacted = _SESSION_REF_RE.sub("local://hh-browser-session/[redacted]", redacted)
    if len(redacted) > max_len:
        return f"{redacted[:max_len]}..."
    return redacted


def sanitize_for_log(value: Any) -> Any:
    """Return log-safe shape for mappings/lists/strings."""
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                sanitized[str(key)] = "[redacted]"
            else:
                sanitized[str(key)] = sanitize_for_log(item)
        return sanitized

    if isinstance(value, list):
        return [sanitize_for_log(item) for item in value[:10]]

    if isinstance(value, tuple):
        return tuple(sanitize_for_log(item) for item in value[:10])

    if isinstance(value, str):
        return redact_text(value)

    return value


def summarize_hh_import_params(params: dict[str, Any]) -> dict[str, Any]:
    """Keep operational HH import context without logging raw query/body."""
    extra_params = params.get("extra_params")
    return {
        "area": params.get("area"),
        "schedule": params.get("schedule"),
        "experience": params.get("experience"),
        "salary_from": params.get("salary_from"),
        "salary_to": params.get("salary_to"),
        "currency": params.get("currency"),
        "per_page": params.get("per_page", 20),
        "pages_limit": params.get("pages_limit", 3),
        "fetch_details": bool(params.get("fetch_details", True)),
        "text_len": len(str(params.get("text") or "")),
        "extra_params_keys": sorted(list(extra_params.keys()))[:20] if isinstance(extra_params, dict) else [],
    }


def safe_error_summary(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {redact_text(str(exc), max_len=200)}"
