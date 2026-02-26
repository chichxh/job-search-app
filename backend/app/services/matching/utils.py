"""Utility helpers for skill matching and evidence extraction."""

from __future__ import annotations

import re
from typing import Optional

TOKEN_RE = re.compile(r"[^\W_]+(?:[.+#-][^\W_]+|[+#]+)*", re.UNICODE)

# Alias graph. Every entry is expanded bidirectionally.
_ALIAS_GROUPS: tuple[set[str], ...] = (
    {"react", "reactjs"},
    {"postgres", "postgresql"},
    {"node", "node.js", "nodejs"},
    {"javascript", "js"},
    {"typescript", "ts"},
    {"drf", "django rest framework", "django-rest-framework"},
    {"oop", "ооп"},
    {"docker compose", "docker-compose"},
    {"grpc", "gRPC".lower()},
)


def tokenize(text: str) -> list[str]:
    """Tokenize text for technical skill matching (c++, c#, node.js, django-rest-framework)."""
    if not text:
        return []
    return [token.lower() for token in TOKEN_RE.findall(text)]


def normalize_skill(text: str) -> str:
    """Normalize skill to lowercased token string joined by spaces."""
    return " ".join(tokenize(text))


def _build_alias_map() -> dict[str, set[str]]:
    alias_map: dict[str, set[str]] = {}
    for group in _ALIAS_GROUPS:
        normalized_group = {" ".join(tokenize(alias)) for alias in group if tokenize(alias)}
        for alias in normalized_group:
            alias_map[alias] = set(normalized_group)
    return alias_map


ALIAS_MAP: dict[str, set[str]] = _build_alias_map()


def contains_token(tokens_set: set[str], term_tokens: list[str]) -> bool:
    """True when all requirement tokens are present as full tokens in tokens_set."""
    if not tokens_set or not term_tokens:
        return False
    return all(token in tokens_set for token in term_tokens)


def extract_profile_tokens(profile_text: str) -> set[str]:
    """Extract normalized token set from profile text."""
    return set(tokenize(profile_text))


def aliases_for_term(term: str) -> set[str]:
    """Return known aliases for a term (normalized), including itself."""
    normalized_term = normalize_skill(term)
    if not normalized_term:
        return set()
    return ALIAS_MAP.get(normalized_term, {normalized_term})


def has_uncertain_match(tokens_set: set[str], normalized_term: str) -> bool:
    """Return True for partial/alias matches that are not full-term matches."""
    if not normalized_term:
        return False

    term_tokens = tokenize(normalized_term)
    if contains_token(tokens_set, term_tokens):
        return False

    for alias in aliases_for_term(normalized_term):
        alias_tokens = tokenize(alias)
        if contains_token(tokens_set, alias_tokens):
            return True
        if any(token in tokens_set for token in alias_tokens):
            return True

    return any(token in tokens_set for token in term_tokens)


def _build_exact_pattern(normalized_term: str) -> re.Pattern[str]:
    escaped = re.escape(normalized_term).replace(r"\ ", r"\\s+")
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def _build_alias_pattern(normalized_alias: str) -> re.Pattern[str]:
    escaped = re.escape(normalized_alias).replace(r"\ ", r"\\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def _find_pattern_span(text: str, pattern: re.Pattern[str]) -> Optional[tuple[int, int]]:
    match = pattern.search(text)
    if not match:
        return None
    return match.start(), match.end()


def _build_snippet(text: str, start: int, end: int, window: int) -> str:
    """Build a context window around the match."""
    if window <= 0:
        return text[start:end]

    center = (start + end) // 2
    half = window // 2
    left = max(0, center - half)
    right = min(len(text), center + half)

    snippet = text[left:right].strip()
    if left > 0:
        snippet = f"...{snippet}"
    if right < len(text):
        snippet = f"{snippet}..."

    return snippet


def find_evidence_snippet(haystack: str, needle: str, window: int = 180) -> tuple[str, float] | None:
    """Find evidence snippet: exact whole-term first, then alias fallback."""
    if not haystack or not needle:
        return None

    normalized_needle = normalize_skill(needle)
    if not normalized_needle:
        return None

    # 1) Exact match by word boundaries first (prevents Git -> GitHub false positive).
    exact_span = _find_pattern_span(haystack, _build_exact_pattern(normalized_needle))
    if exact_span:
        return _build_snippet(haystack, exact_span[0], exact_span[1], window), 1.0

    # 2) Alias fallback with strict token boundaries.
    for alias in aliases_for_term(normalized_needle) - {normalized_needle}:
        alias_span = _find_pattern_span(haystack, _build_alias_pattern(alias))
        if alias_span:
            return _build_snippet(haystack, alias_span[0], alias_span[1], window), 0.8

    return None
