import os

from celery import Celery
from celery.schedules import crontab

from app.services.embeddings.provider import validate_embedding_configuration

SYNC_INTERVAL_MINUTES = int(os.getenv("SAVED_SEARCH_SYNC_INTERVAL_MINUTES", "5"))

validate_embedding_configuration()

celery_app = Celery(
    "job_search_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)

celery_app.conf.beat_schedule = {
    "schedule-saved-search-sync": {
        "task": "app.tasks.hh_import_tasks.schedule_saved_search_sync",
        "schedule": crontab(minute=f"*/{SYNC_INTERVAL_MINUTES}"),
    }
}

celery_app.autodiscover_tasks(["app"])
