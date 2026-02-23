"""Utility helpers for skill matching and evidence extraction."""

from __future__ import annotations

import re
from typing import Optional

# Minimal alias map for common tech skill variants.
_ALIAS_MAP: dict[str, set[str]] = {
    "react": {"react", "reactjs"},
    "postgresql": {"postgresql", "postgres"},
    "nodejs": {"nodejs", "node", "node.js"},
    "javascript": {"javascript", "js"},
    "typescript": {"typescript", "ts"},
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[.#-][A-Za-z0-9]+|[+#]+)*")
_EDGE_ALLOWED = set("+#")


def normalize_skill(text: str) -> str:
    """Normalize a skill string without breaking technical forms like C++, C#, node.js."""
    if not text:
        return ""

    normalized = re.sub(r"\s+", " ", text.lower().strip())
    if not normalized:
        return ""

    start = 0
    end = len(normalized)

    while start < end:
        char = normalized[start]
        if char.isalnum() or char in _EDGE_ALLOWED:
            break
        start += 1

    while end > start:
        char = normalized[end - 1]
        if char.isalnum() or char in _EDGE_ALLOWED:
            break
        end -= 1

    return normalized[start:end].strip()


def _aliases_for(skill: str) -> set[str]:
    """Return known aliases for the given skill (including itself)."""
    normalized_skill = normalize_skill(skill)
    if not normalized_skill:
        return set()

    aliases = {normalized_skill}
    for _, variants in _ALIAS_MAP.items():
        normalized_variants = {normalize_skill(v) for v in variants}
        if normalized_skill in normalized_variants:
            aliases.update(normalized_variants)
            break

    return {alias for alias in aliases if alias}


def extract_profile_tokens(profile_text: str) -> set[str]:
    """Extract normalized token set from profile text, preserving technical words."""
    if not profile_text:
        return set()

    tokens = set()
    for raw in _TOKEN_RE.findall(profile_text):
        normalized = normalize_skill(raw)
        if normalized:
            tokens.add(normalized)
    return tokens


def _find_match_span(text: str, candidate: str) -> Optional[tuple[int, int]]:
    """Find a candidate as a token-level match in text."""
    if not candidate:
        return None

    normalized_candidate = normalize_skill(candidate)
    for token_match in _TOKEN_RE.finditer(text):
        if normalize_skill(token_match.group(0)) == normalized_candidate:
            return token_match.start(), token_match.end()
    return None


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
    """Find evidence snippet for a skill in text with exact/alias confidence scoring."""
    if not haystack or not needle:
        return None

    normalized_needle = normalize_skill(needle)
    if not normalized_needle:
        return None

    # 1) Exact normalized needle first.
    exact_span = _find_match_span(haystack, normalized_needle)
    if exact_span:
        return _build_snippet(haystack, exact_span[0], exact_span[1], window), 1.0

    # 2) Alias matches.
    aliases = _aliases_for(normalized_needle) - {normalized_needle}
    for alias in aliases:
        alias_span = _find_match_span(haystack, alias)
        if alias_span:
            return _build_snippet(haystack, alias_span[0], alias_span[1], window), 0.8

    # 3) Partial normalized fallback.
    normalized_haystack = normalize_skill(haystack)
    partial_index = normalized_haystack.find(normalized_needle)
    if partial_index != -1:
        start = max(0, partial_index)
        end = min(len(haystack), partial_index + len(normalized_needle))
        return _build_snippet(haystack, start, end, window), 0.8

    return None


def self_check_normalize_skill() -> dict[str, str]:
    """Tiny built-in checks for normalize_skill behavior."""
    samples = ["  C++  ", "(ReactJS)", " node.js ", "  ", "...Postgres!!!"]
    return {sample: normalize_skill(sample) for sample in samples}


def self_check_extract_profile_tokens() -> set[str]:
    """Tiny built-in checks for token extraction behavior."""
    sample = "Senior Node.js engineer, C++, ReactJS, PostgreSQL/Postgres"
    return extract_profile_tokens(sample)


def self_check_find_evidence_snippet() -> dict[str, tuple[str, float] | None]:
    """Tiny built-in checks for evidence extraction behavior."""
    haystack = (
        "Built APIs with Node.js and PostgreSQL. "
        "Used React in frontend and mentored junior engineers."
    )
    return {
        "node": find_evidence_snippet(haystack, "node"),
        "postgres": find_evidence_snippet(haystack, "postgres"),
        "reactjs": find_evidence_snippet(haystack, "reactjs"),
        "golang": find_evidence_snippet(haystack, "golang"),
    }
