"""Celery tasks package."""

from app.tasks.embedding_tasks import build_profile_embedding, build_vacancy_embedding
from app.tasks.hh_import_tasks import import_hh_vacancies_task, sync_saved_search_task

__all__ = [
    "import_hh_vacancies_task",
    "sync_saved_search_task",
    "build_vacancy_embedding",
    "build_profile_embedding",
]
