import re

from app.services.matching.utils import tokenize
from app.services.vacancy_parsing.line_classifier import classify_line
from app.services.vacancy_parsing.requirement_markers import STARTS_LIKE_REQUIREMENT


_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "Flask": ("flask",),
    "PostgreSQL": ("postgresql", "postgres"),
    "Redis": ("redis",),
    "Kafka": ("kafka",),
    "RabbitMQ": ("rabbitmq", "rabbit mq"),
    "Celery": ("celery",),
    "Docker": ("docker",),
    "Docker Compose": ("docker compose", "docker-compose"),
    "Kubernetes": ("kubernetes", "k8s"),
    "React": ("react",),
    "TypeScript": ("typescript", "type script"),
    "Airflow": ("airflow",),
    "Prometheus": ("prometheus",),
    "Grafana": ("grafana",),
    "gRPC": ("grpc", "g rpc"),
    "REST": ("rest", "rest api"),
    "WebSocket": ("websocket", "web socket"),
    "Django REST Framework": ("drf", "django rest framework"),
    "ООП": ("ооп", "oop", "object oriented programming", "object-oriented programming"),
    "async": ("async", "asyncio", "асинхрон", "асинхронность", "асинхронное", "асинхронный"),
    "pytest": ("pytest", "py test"),
    "Git": ("git",),
}


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s-]", " ", lowered, flags=re.UNICODE)
    cleaned = cleaned.replace("-", " ")
    return " ".join(cleaned.split())


def _normalize_skill_key(text: str) -> str:
    """Normalize skill key preserving technical symbols like +, #, . and -."""
    return " ".join(tokenize(text))


_HARD_MARKERS = ("обязательно", "необходимо", "требуется")
_NICE_MARKERS = ("плюсом будет", "желательно")
_HARD_SECTION_MARKERS = ("требования", "мы ожидаем", "ожидания от кандидата")
_NICE_SECTION_MARKERS = ("будет плюсом", "плюсом будет", "желательно")
_STOP_SECTION_MARKERS = ("обязанности", "условия", "мы предлагаем", "о компании", "задачи")


def _split_sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"[\n\.!?;]+", text) if chunk.strip()]


def _find_marker_context(text: str, markers: tuple[str, ...]) -> list[str]:
    normalized_markers = tuple(_normalize_text(marker) for marker in markers)
    contexts: list[str] = []
    for sentence in _split_sentences(text.lower()):
        normalized_sentence = _normalize_text(sentence)
        if any(marker in normalized_sentence for marker in normalized_markers):
            contexts.append(normalized_sentence)
    return contexts


def _extract_section_blocks(clean_text: str) -> tuple[str, str]:
    hard_lines: list[str] = []
    nice_lines: list[str] = []
    current_section: str | None = None

    for raw_line in clean_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        normalized = _normalize_text(stripped)
        if any(marker in normalized for marker in _HARD_SECTION_MARKERS):
            current_section = "hard"
            continue
        if any(marker in normalized for marker in _NICE_SECTION_MARKERS):
            current_section = "nice"
            continue
        if any(marker in normalized for marker in _STOP_SECTION_MARKERS):
            current_section = None
            continue

        content = stripped.lstrip("-•*0123456789.) ").strip()
        if not content or current_section is None:
            continue

        if current_section == "hard":
            hard_lines.append(content)
        elif current_section == "nice":
            nice_lines.append(content)

    return "\n".join(hard_lines), "\n".join(nice_lines)


def _extract_skills_from_text(text: str, *, is_hard: bool) -> list[dict]:
    line_tokens = tokenize(text)
    if not line_tokens:
        return []

    requirements: list[dict] = []
    for raw_text, aliases in _SKILL_ALIASES.items():
        matched = False
        for alias in aliases:
            alias_tokens = tokenize(alias)
            if _contains_token_sequence(line_tokens, alias_tokens):
                matched = True
                break

        if matched:
            requirements.append(
                {
                    "kind": "skill",
                    "raw_text": raw_text,
                    "normalized_key": _normalize_skill_key(raw_text),
                    "is_hard": is_hard,
                    "weight": 3 if is_hard else 1,
                }
            )
    return requirements


def _contains_token_sequence(tokens: list[str], sequence: list[str]) -> bool:
    if not tokens or not sequence:
        return False

    sequence_len = len(sequence)
    if sequence_len > len(tokens):
        return False

    for idx in range(len(tokens) - sequence_len + 1):
        if tokens[idx : idx + sequence_len] == sequence:
            return True
    return False


def _starts_like_requirement(line: str) -> bool:
    normalized = _normalize_text(line)
    return any(normalized.startswith(prefix) for prefix in STARTS_LIKE_REQUIREMENT)


def _extract_skills_from_lines(lines: list[str], *, is_hard: bool) -> list[dict]:
    requirements: list[dict] = []
    for line in lines:
        requirements.extend(_extract_skills_from_text(line, is_hard=is_hard))
    return requirements


def extract_requirements_from_sections(sections_json: dict) -> list[dict]:
    deduped: dict[str, dict] = {}

    def upsert(requirement: dict) -> None:
        key = requirement["normalized_key"] or requirement["raw_text"]
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = requirement
            return

        if requirement["is_hard"] and not existing["is_hard"]:
            deduped[key] = requirement

    def section_source(section: str, line_class: str) -> str:
        if section == "requirements" and line_class == "must":
            return "text_requirements"
        if line_class == "nice":
            return "text_plus"
        return "text_other_fallback"

    for section_name in ("requirements", "nice_to_have"):
        lines = ((sections_json.get(section_name) or {}).get("lines") or [])
        for line in lines:
            line_class = classify_line(line, section_name)
            if line_class == "other":
                continue

            is_hard = line_class == "must"
            source = section_source(section_name, line_class)
            for req in _extract_skills_from_text(line, is_hard=is_hard):
                req["weight"] = 3 if line_class == "must" else 1 if line_class == "nice" else 0
                req["source"] = source
                upsert(req)

    if len(deduped) < 3:
        other_lines = ((sections_json.get("other") or {}).get("lines") or [])
        for line in other_lines:
            line_class = classify_line(line, "other")
            should_add = line_class in {"must", "nice"} or _starts_like_requirement(line)
            if not should_add:
                continue

            for req in _extract_skills_from_text(line, is_hard=False):
                req["is_hard"] = False
                req["weight"] = 1
                req["source"] = "text_other_fallback"
                upsert(req)

    return list(deduped.values())


def extract_requirements_fallback(plain_text: str) -> list[dict]:
    requirements: dict[str, dict] = {}
    normalized_hard_markers = tuple(_normalize_text(marker) for marker in _HARD_MARKERS)

    for line in plain_text.splitlines():
        normalized_line = _normalize_text(line)
        if not normalized_line:
            continue

        is_hard = any(marker in normalized_line for marker in normalized_hard_markers)
        for requirement in _extract_skills_from_text(line, is_hard=is_hard):
            key = requirement["normalized_key"] or requirement["raw_text"]
            existing = requirements.get(key)
            if existing is None or (requirement["is_hard"] and not existing["is_hard"]):
                requirements[key] = requirement

    if requirements:
        return list(requirements.values())

    return extract_skill_requirements(plain_text)


def extract_requirements_from_description(clean_text: str) -> list[dict]:
    hard_block, nice_block = _extract_section_blocks(clean_text)
    extracted = [
        *_extract_skills_from_text(hard_block, is_hard=True),
        *_extract_skills_from_text(nice_block, is_hard=False),
    ]

    deduped: dict[str, dict] = {}
    for requirement in extracted:
        key = requirement["normalized_key"] or requirement["raw_text"]
        existing = deduped.get(key)
        if existing is None or (requirement["is_hard"] and not existing["is_hard"]):
            deduped[key] = requirement
    return list(deduped.values())


def extract_skill_requirements(text: str) -> list[dict]:
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return []

    padded_text = f" {normalized_text} "
    hard_contexts = _find_marker_context(text, _HARD_MARKERS)
    nice_contexts = _find_marker_context(text, _NICE_MARKERS)
    requirements: list[dict] = []

    for raw_text, aliases in _SKILL_ALIASES.items():
        matched = False
        for alias in aliases:
            normalized_alias = _normalize_text(alias)
            if normalized_alias and f" {normalized_alias} " in padded_text:
                matched = True
                break

        if not matched:
            continue

        normalized_skill = _normalize_skill_key(raw_text)
        in_hard_context = any(f" {normalized_skill} " in f" {context} " for context in hard_contexts)
        in_nice_context = any(f" {normalized_skill} " in f" {context} " for context in nice_contexts)
        is_hard = in_hard_context and not in_nice_context

        requirements.append(
            {
                "kind": "skill",
                "raw_text": raw_text,
                "normalized_key": normalized_skill,
                "is_hard": is_hard,
                "weight": 3 if is_hard else 1,
            }
        )

    return requirements
