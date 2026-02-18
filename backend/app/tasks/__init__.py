"""Celery tasks package."""

from app.tasks.hh_import_tasks import import_hh_vacancies_task

__all__ = ["import_hh_vacancies_task"]
