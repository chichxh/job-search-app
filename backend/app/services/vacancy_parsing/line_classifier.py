"""Line-level classification utilities for vacancy requirement parsing."""

from __future__ import annotations

import re
from typing import Literal

from .requirement_markers import EXCEPTIONS, LINE_MARKERS, SECTION_HEADERS, STARTS_LIKE_REQUIREMENT

LineClass = Literal["must", "nice", "other"]


def normalize_line(s: str) -> str:
    """Normalize line text for marker matching."""
    return " ".join(s.lower().strip().split())


def is_section_header(line: str) -> str | None:
    """Return section key for header-like line, otherwise None."""
    normalized = normalize_line(line).rstrip(":")
    if not normalized:
        return None

    for section, markers in SECTION_HEADERS.items():
        for marker in markers:
            marker_norm = normalize_line(marker).rstrip(":")
            if normalized == marker_norm:
                return section

    return None


def _contains_any(line: str, markers: list[str]) -> bool:
    return any(marker in line for marker in markers)


def _matches_any_pattern(line: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, line) for pattern in patterns)


def classify_line(line: str, current_section: str | None) -> LineClass:
    """Classify a vacancy line as must/nice/other according to priority rules."""
    normalized = normalize_line(line)
    if not normalized:
        return "other"

    nice_markers = LINE_MARKERS["nice"]
    must_markers = LINE_MARKERS["must"]

    if current_section == "nice_to_have":
        return "nice"

    if current_section == "requirements":
        if _contains_any(normalized, nice_markers):
            return "nice"
        return "must"

    if _contains_any(normalized, nice_markers):
        return "nice"

    if _contains_any(normalized, must_markers):
        only_patterns = EXCEPTIONS.get("only_format_patterns", [])
        if "только" in normalized and _matches_any_pattern(normalized, only_patterns):
            return "other"
        return "must"

    if any(normalized.startswith(prefix) for prefix in STARTS_LIKE_REQUIREMENT):
        return "must"

    return "other"


# Self-check demo:
# - classify_line("Будет плюсом опыт с Kafka", current_section=None) == "nice"
# - classify_line("Опыт работы с PostgreSQL от 3 лет", current_section=None) == "must"
# - classify_line("Только офис, гибрид недоступен", current_section=None) == "other"
# - classify_line("Docker и Kubernetes", current_section="requirements") == "must"
