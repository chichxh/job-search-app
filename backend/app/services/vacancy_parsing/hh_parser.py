from __future__ import annotations

import re

from app.utils.text_clean import strip_html

from .line_classifier import is_section_header
from .requirement_markers import SECTION_HEADERS

VERSION = "hh_sections_v2"

_BULLET_PREFIX_RE = re.compile(
    r"^\s*(?:[-*•●◦▪▫‣∙]+|\d+[\.)]|[a-zа-я]\)|[ivxlcdm]+\))\s+",
    flags=re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_line(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip())


def _strip_bullet_prefix(value: str) -> str:
    cleaned = value.strip()
    while cleaned:
        updated = _BULLET_PREFIX_RE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated.strip()
    return cleaned


def _header_section_from_prefix(prefix: str) -> str | None:
    section = is_section_header(prefix)
    if section:
        return section

    normalized_prefix = _normalize_line(prefix).lower().rstrip(":-–—")
    if not normalized_prefix:
        return None

    for candidate_section, markers in SECTION_HEADERS.items():
        for marker in markers:
            marker_value = _normalize_line(marker).lower().rstrip(":-–—")
            if marker_value == normalized_prefix:
                return candidate_section
    return None


def _detect_header(line: str) -> tuple[str | None, str]:
    cleaned_line = _normalize_line(line)
    if not cleaned_line:
        return None, ""

    direct_section = is_section_header(cleaned_line)
    if direct_section:
        return direct_section, ""

    separator_match = re.search(r"\s*[:\-–—]\s*", cleaned_line)
    if not separator_match:
        return None, ""

    prefix = cleaned_line[: separator_match.start()]
    section = _header_section_from_prefix(prefix)
    if not section:
        return None, ""

    remainder = cleaned_line[separator_match.end() :]
    return section, remainder


def _section_payload(lines: list[str]) -> dict[str, list[str] | str]:
    return {"lines": lines, "text": "\n".join(lines)}


def parse_hh_description(html: str) -> dict:
    plain_text = strip_html(html or "")

    sections: dict[str, list[str]] = {
        "responsibilities": [],
        "requirements": [],
        "nice_to_have": [],
        "conditions": [],
        "other": [],
    }

    current_section = "other"

    for raw_line in plain_text.splitlines():
        line = _normalize_line(_strip_bullet_prefix(raw_line))
        if not line:
            continue

        detected_section, remainder = _detect_header(line)
        if detected_section:
            current_section = detected_section
            remainder = _normalize_line(_strip_bullet_prefix(remainder))
            if remainder:
                sections[detected_section].append(remainder)
            continue

        sections[current_section].append(line)

    quality_score = 0.0
    if len(sections["requirements"]) >= 3:
        quality_score += 0.45
    if len(sections["responsibilities"]) >= 1:
        quality_score += 0.15
    if len(sections["conditions"]) >= 1:
        quality_score += 0.10
    if len(plain_text) >= 600:
        quality_score += 0.20

    total_lines = sum(len(lines) for lines in sections.values())
    if total_lines >= 8:
        quality_score += 0.20

    if total_lines > 0 and len(sections["other"]) == total_lines:
        quality_score -= 0.25

    result_sections = {name: _section_payload(lines) for name, lines in sections.items()}

    return {
        "plain_text": plain_text,
        "sections": result_sections,
        "quality_score": max(0.0, min(1.0, round(quality_score, 4))),
        "version": VERSION,
    }


def demo_parse() -> dict:
    """Small self-check helper for local manual runs."""

    demo_html = """
    <p><strong>Обязанности:</strong></p>
    <ul><li>Разрабатывать backend-сервисы</li><li>Писать тесты</li></ul>
    <p><strong>Требования</strong></p>
    <ul><li>Python 3</li><li>FastAPI</li><li>SQL</li></ul>
    <p><strong>Мы предлагаем:</strong></p>
    <ul><li>Удаленную работу</li></ul>
    """
    return parse_hh_description(demo_html)
