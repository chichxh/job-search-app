from __future__ import annotations

from typing import Any, Mapping

from app.llm import LLMMessage


_SYSTEM_RULES = """Ты — ассистент по генерации резюме и сопроводительных писем.
Строгие правила (обязательны):
1) НИКОГДА не выдумывай факты.
2) Используй только факты из входных данных: profile_facts, vacancy_facts, tailoring.
3) Запрещено придумывать или дополнять: опыт, даты, компании, должности, стек, сертификаты, метрики, достижения.
4) Если фактов недостаточно для корректного текста, добавь в конце блок:
   НУЖНО УТОЧНИТЬ
   - вопрос 1
   - вопрос 2
5) Не маскируй отсутствие фактов общими фразами. Лучше явно попроси уточнение.
"""


def build_resume_prompt(
    profile_facts: Mapping[str, Any],
    vacancy_facts: Mapping[str, Any],
    tailoring: Mapping[str, Any],
) -> list[LLMMessage]:
    user_prompt = (
        "Сформируй резюме строго в markdown.\n"
        "Обязательные секции и порядок: Summary, Skills, Experience, Projects, Education.\n"
        "Если данных для любой секции не хватает — добавь блок 'НУЖНО УТОЧНИТЬ' с вопросами.\n\n"
        f"{_build_shared_facts_block(profile_facts, vacancy_facts, tailoring)}"
    )
    return [
        LLMMessage(role="system", content=_SYSTEM_RULES),
        LLMMessage(role="user", content=user_prompt),
    ]


def build_cover_letter_prompt(
    profile_facts: Mapping[str, Any],
    vacancy_facts: Mapping[str, Any],
    tailoring: Mapping[str, Any],
) -> list[LLMMessage]:
    user_prompt = (
        "Сформируй сопроводительное письмо.\n"
        "Формат: 200-350 слов, 3-5 абзацев, без воды.\n"
        "Обязательно используй 2-3 конкретных доказательства из фактов профиля/evidence snippets.\n"
        "Если данных недостаточно — добавь блок 'НУЖНО УТОЧНИТЬ' с вопросами.\n\n"
        f"{_build_shared_facts_block(profile_facts, vacancy_facts, tailoring)}"
    )
    return [
        LLMMessage(role="system", content=_SYSTEM_RULES),
        LLMMessage(role="user", content=user_prompt),
    ]


def _build_shared_facts_block(
    profile_facts: Mapping[str, Any],
    vacancy_facts: Mapping[str, Any],
    tailoring: Mapping[str, Any],
) -> str:
    style = tailoring.get("style") or tailoring.get("tone") or "не указан"
    sections_json = vacancy_facts.get("sections_json") or {}
    requirements = _extract_requirements_lines(sections_json)

    parts = [
        "[ВАКАНСИЯ]",
        f"- title: {_to_text(vacancy_facts.get('title'))}",
        f"- company: {_to_text(vacancy_facts.get('company') or vacancy_facts.get('company_name'))}",
        f"- location: {_to_text(vacancy_facts.get('location'))}",
        "- requirements:",
        _to_bullets(requirements, fallback="нет данных"),
        "",
        "[TAILORING]",
        "- keywords_to_add:",
        _to_bullets(tailoring.get("keywords_to_add"), fallback="нет данных"),
        "- missing_must:",
        _to_bullets(
            tailoring.get("missing_must") or tailoring.get("keywords_missing_must"),
            fallback="нет данных",
        ),
        "- missing_nice:",
        _to_bullets(
            tailoring.get("missing_nice") or tailoring.get("keywords_missing_nice"),
            fallback="нет данных",
        ),
        "- cover_letter_points:",
        _to_bullets(tailoring.get("cover_letter_points"), fallback="нет данных"),
        "- evidence snippets:",
        _to_bullets(_extract_evidence_snippets(tailoring), fallback="нет данных"),
        f"- style: {_to_text(style)}",
        "",
        "[ПРОФИЛЬ]",
        f"- summary_about: {_to_text(profile_facts.get('summary_about'))}",
        "- skills (with levels):",
        _format_skills(profile_facts.get("skills")),
        "- latest experiences:",
        _to_bullets(profile_facts.get("experiences"), fallback="нет данных"),
        "- latest projects:",
        _to_bullets(profile_facts.get("projects"), fallback="нет данных"),
        "- latest achievements:",
        _to_bullets(profile_facts.get("achievements"), fallback="нет данных"),
    ]
    return "\n".join(parts)


def _extract_requirements_lines(sections_json: Any) -> list[str]:
    if not isinstance(sections_json, Mapping):
        return []

    result: list[str] = []
    for section_name in ("requirements", "responsibilities", "conditions", "other"):
        section = sections_json.get(section_name)
        if not isinstance(section, Mapping):
            continue
        lines = section.get("lines")
        if isinstance(lines, list):
            for line in lines:
                text = _to_text(line)
                if text != "не указано":
                    result.append(text)
    return result


def _extract_evidence_snippets(tailoring: Mapping[str, Any]) -> list[str]:
    evidence = tailoring.get("evidence") or tailoring.get("evidence_snippets")
    if not isinstance(evidence, list):
        return []

    snippets: list[str] = []
    for item in evidence:
        if isinstance(item, Mapping):
            text = item.get("text") or item.get("evidence_text")
            parsed = _to_text(text)
            if parsed != "не указано":
                snippets.append(parsed)
        else:
            parsed = _to_text(item)
            if parsed != "не указано":
                snippets.append(parsed)
    return snippets


def _format_skills(skills: Any) -> str:
    if not isinstance(skills, list) or not skills:
        return "- нет данных"

    lines: list[str] = []
    for item in skills:
        if isinstance(item, Mapping):
            name = _to_text(item.get("name") or item.get("skill"))
            level = _to_text(item.get("level"))
            if level == "не указано":
                lines.append(f"- {name}")
            else:
                lines.append(f"- {name} ({level})")
        else:
            lines.append(f"- {_to_text(item)}")
    return "\n".join(lines)


def _to_bullets(value: Any, *, fallback: str = "не указано") -> str:
    if isinstance(value, list) and value:
        return "\n".join(f"- {_to_text(item)}" for item in value)
    return f"- {fallback}"


def _to_text(value: Any) -> str:
    if value is None:
        return "не указано"
    text = str(value).strip()
    return text or "не указано"
