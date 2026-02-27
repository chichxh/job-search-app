import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, cast


LLMProvider = Literal["gigachat", "openai"]


@dataclass(frozen=True)
class LLMSettings:
    provider: LLMProvider
    model: str
    temperature: float
    max_tokens: int
    gigachat_auth_key: str | None
    gigachat_scope: str
    gigachat_oauth_url: str
    gigachat_api_base: str
    gigachat_verify_ssl: bool
    openai_api_key: str | None


def _as_bool(raw_value: str | None, *, default: bool) -> bool:
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    raise ValueError(
        f"Invalid boolean value for GIGACHAT_VERIFY_SSL: {raw_value!r}. "
        "Use one of: true/false, 1/0, yes/no, on/off."
    )


@lru_cache(maxsize=1)
def get_llm_settings() -> LLMSettings:
    provider_raw = os.getenv("LLM_PROVIDER", "gigachat").strip().lower()
    if provider_raw not in {"gigachat", "openai"}:
        raise ValueError(
            "Unsupported LLM_PROVIDER. Expected one of: 'gigachat', 'openai'. "
            f"Got: {provider_raw!r}"
        )

    return LLMSettings(
        provider=cast(LLMProvider, provider_raw),
        model=os.getenv("LLM_MODEL", "GigaChat"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1200")),
        gigachat_auth_key=os.getenv("GIGACHAT_AUTH_KEY"),
        gigachat_scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        gigachat_oauth_url=os.getenv(
            "GIGACHAT_OAUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        ),
        gigachat_api_base=os.getenv("GIGACHAT_API_BASE", "https://gigachat.devices.sberbank.ru"),
        gigachat_verify_ssl=_as_bool(os.getenv("GIGACHAT_VERIFY_SSL"), default=True),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


def validate_llm_settings() -> LLMSettings:
    """Проверяет обязательные параметры для выбранного LLM-провайдера."""

    settings = get_llm_settings()

    if settings.provider == "gigachat" and not settings.gigachat_auth_key:
        raise ValueError(
            "LLM provider is set to 'gigachat', but GIGACHAT_AUTH_KEY is not configured. "
            "Set GIGACHAT_AUTH_KEY in environment (Basic auth key from GigaChat cabinet)."
        )

    if settings.provider == "openai" and not settings.openai_api_key:
        raise ValueError(
            "LLM provider is set to 'openai', but OPENAI_API_KEY is not configured. "
            "Set OPENAI_API_KEY in environment."
        )

    return settings


def reset_llm_settings_cache() -> None:
    """Utility for tests/dev to re-read env after changes."""

    get_llm_settings.cache_clear()
