from __future__ import annotations

import re

from app.utils.text_clean import strip_html

VERSION = "hh_sections_v1"

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "responsibilities": ("обязанности", "задачи", "что делать"),
    "requirements": (
        "требования",
        "мы ожидаем",
        "ожидания от кандидата",
        "требования к кандидату",
    ),
    "nice_to_have": ("будет плюсом", "желательно", "приветствуется", "nice to have"),
    "conditions": ("условия", "мы предлагаем", "компенсация", "benefits"),
}

_BULLET_PREFIX_RE = re.compile(
    r"^\s*(?:[-*•●◦▪▫‣∙]+|\d+[\.)]|[a-zа-я]\)|[ivxlcdm]+\))\s+",
    flags=re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_header_candidate(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip().lower())


def _strip_bullet_prefix(value: str) -> str:
    cleaned = value.strip()
    while cleaned:
        updated = _BULLET_PREFIX_RE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated.strip()
    return cleaned


def _detect_header(value: str) -> tuple[str | None, str]:
    normalized = _normalize_header_candidate(value)
    for section, aliases in _SECTION_ALIASES.items():
        for alias in aliases:
            if normalized.rstrip(":-–— ") == alias:
                return section, ""

            match = re.match(rf"^{re.escape(alias)}\s*[:\-–—]\s*(.+)$", normalized, flags=re.IGNORECASE)
            if match:
                return section, match.group(1).strip()
    return None, ""


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

    current_section: str | None = None

    for raw_line in plain_text.splitlines():
        line = _strip_bullet_prefix(raw_line)
        if not line:
            continue

        detected_section, remainder = _detect_header(line)
        if detected_section:
            current_section = detected_section
            remainder = _strip_bullet_prefix(remainder)
            if remainder:
                sections[detected_section].append(remainder)
            continue

        target = current_section or "other"
        sections[target].append(line)

    quality_score = 0.0
    if len(sections["requirements"]) >= 3:
        quality_score += 0.35
    if len(sections["responsibilities"]) >= 1:
        quality_score += 0.15
    if len(sections["conditions"]) >= 1:
        quality_score += 0.10
    if len(plain_text) >= 600:
        quality_score += 0.20

    total_lines = sum(len(lines) for lines in sections.values())
    if total_lines >= 8:
        quality_score += 0.20

    result_sections = {name: _section_payload(lines) for name, lines in sections.items()}

    return {
        "plain_text": plain_text,
        "sections": result_sections,
        "quality_score": min(1.0, round(quality_score, 4)),
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
