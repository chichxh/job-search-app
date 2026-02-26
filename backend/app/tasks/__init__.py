"""Celery tasks package."""

from app.tasks.embedding_tasks import (
    build_profile_embedding,
    build_vacancy_embedding,
    rebuild_profile_embeddings,
    rebuild_vacancy_embeddings,
)
from app.tasks.hh_import_tasks import import_hh_vacancies_task, sync_saved_search_task
from app.tasks.matching_tasks import compute_profile_recommendations
from app.tasks.vacancy_parsing_tasks import backfill_hh_parsed

__all__ = [
    "import_hh_vacancies_task",
    "sync_saved_search_task",
    "build_vacancy_embedding",
    "build_profile_embedding",
    "rebuild_vacancy_embeddings",
    "rebuild_profile_embeddings",
    "compute_profile_recommendations",
    "backfill_hh_parsed",
]
