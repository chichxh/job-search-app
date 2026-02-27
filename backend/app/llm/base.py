from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(slots=True)
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(slots=True)
class LLMRequest:
    messages: list[LLMMessage]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None


@dataclass(slots=True)
class LLMResponse:
    text: str
    provider: str
    model: str | None = None
    usage: dict | None = None
    raw: dict | None = None


class LLMClient(Protocol):
    def generate(self, req: LLMRequest) -> LLMResponse:
        ...


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMAuthError(LLMError):
    """Authentication or authorization error from LLM provider."""


class LLMRateLimitError(LLMError):
    """Rate limit exceeded on LLM provider side."""


class LLMUpstreamError(LLMError):
    """Unexpected upstream failure from LLM provider."""
