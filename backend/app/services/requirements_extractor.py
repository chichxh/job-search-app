import re


_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
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
    "DRF": ("drf", "django rest framework"),
    "pytest": ("pytest", "py test"),
    "Git": ("git",),
}


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s-]", " ", lowered, flags=re.UNICODE)
    cleaned = cleaned.replace("-", " ")
    return " ".join(cleaned.split())


_HARD_MARKERS = ("обязательно", "необходимо", "требуется")
_NICE_MARKERS = ("плюсом будет", "желательно")


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

        normalized_skill = _normalize_text(raw_text)
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
