from __future__ import annotations

from functools import lru_cache

from app.core.config import get_llm_settings
from app.llm.base import LLMClient
from app.llm.providers import GigaChatClient


@lru_cache(maxsize=1)
def _get_gigachat_client() -> GigaChatClient:
    return GigaChatClient()


def get_llm_client() -> LLMClient:
    """Return configured LLM client as process-wide singleton."""

    settings = get_llm_settings()

    if settings.provider == "gigachat":
        return _get_gigachat_client()

    if settings.provider == "openai":
        raise NotImplementedError(
            "LLM provider 'openai' is not implemented yet. "
            "Switch LLM_PROVIDER to 'gigachat' or add OpenAI client implementation."
        )

    raise ValueError(f"Unsupported LLM provider: {settings.provider}")
