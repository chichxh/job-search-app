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


def extract_skill_requirements(text: str) -> list[dict]:
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return []

    padded_text = f" {normalized_text} "
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

        requirements.append(
            {
                "kind": "skill",
                "raw_text": raw_text,
                "normalized_key": _normalize_text(raw_text),
                "is_hard": False,
                "weight": 1,
            }
        )

    return requirements
