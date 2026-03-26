import asyncio
import logging
from time import perf_counter
from typing import Any

from sqlalchemy import select

from app.celery_app import celery_app
from app.db.models import SavedSearch
from app.db.session import SessionLocal
from app.integrations.hh_client import HHClient
from app.services.hh_import_service import HHImportFilters, HHImportService
from app.tasks.observability import failure_summary, mark_task_started, success_meta, task_name

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.hh_import_tasks.import_hh_vacancies_task")
def import_hh_vacancies_task(self, params: dict[str, Any]) -> dict[str, Any]:
    """Import vacancies from HH and store them in Postgres."""

    current_task_name = task_name(self, "import_hh_vacancies_task")
    timer_started = perf_counter()
    started_at = mark_task_started(
        self,
        name=current_task_name,
        message="HH import in progress",
        extra={"flow": "hh_import"},
    )
    logger.info("Task started | task=%s params=%s", current_task_name, params)
    db = SessionLocal()
    try:
        result = asyncio.run(_run_import(db, params))
        payload = {
            "saved_count": result.saved_count,
            "updated_count": result.updated_count,
            "pages_processed": result.pages_processed,
            "errors_count": result.errors_count,
        }
        payload.update(
            success_meta(
                current_task_name,
                started_at=started_at,
                timer_started=timer_started,
                message="HH import finished",
            )
        )
        logger.info("Task finished | task=%s result=%s", current_task_name, payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Task failed | task=%s params=%s summary=%s",
            current_task_name,
            params,
            failure_summary(exc),
        )
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.hh_import_tasks.schedule_saved_search_sync")
def schedule_saved_search_sync(self) -> dict[str, int]:
    """Beat task that enqueues sync jobs for all active saved searches."""

    current_task_name = task_name(self, "schedule_saved_search_sync")
    timer_started = perf_counter()
    started_at = mark_task_started(
        self,
        name=current_task_name,
        message="Saved searches scheduling in progress",
        extra={"flow": "saved_search_sync_scheduler"},
    )
    logger.info("Task started | task=%s", current_task_name)
    db = SessionLocal()
    try:
        stmt = select(SavedSearch.id).where(SavedSearch.is_active.is_(True))
        saved_search_ids = list(db.execute(stmt).scalars().all())

        for search_id in saved_search_ids:
            sync_saved_search_task.delay(search_id)

        payload: dict[str, int | dict[str, Any]] = {"enqueued": len(saved_search_ids)}
        payload.update(
            success_meta(
                current_task_name,
                started_at=started_at,
                timer_started=timer_started,
                message="Saved searches scheduling finished",
            )
        )
        logger.info("Task finished | task=%s enqueued_saved_search_sync=%s", current_task_name, len(saved_search_ids))
        return payload
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.hh_import_tasks.sync_saved_search_task")
def sync_saved_search_task(self, saved_search_id: int) -> dict[str, Any]:
    """Sync a single SavedSearch with HH and update sync markers."""

    current_task_name = task_name(self, "sync_saved_search_task")
    timer_started = perf_counter()
    started_at = mark_task_started(
        self,
        name=current_task_name,
        message="Saved search sync in progress",
        extra={"flow": "saved_search_sync", "saved_search_id": saved_search_id},
    )
    logger.info("Task started | task=%s saved_search_id=%s", current_task_name, saved_search_id)
    db = SessionLocal()
    try:
        payload = asyncio.run(_run_saved_search_sync(db, saved_search_id))
        payload.update(
            success_meta(
                current_task_name,
                started_at=started_at,
                timer_started=timer_started,
                message="Saved search sync finished",
            )
        )
        logger.info("Task finished | task=%s payload=%s", current_task_name, payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Task failed | task=%s saved_search_id=%s summary=%s",
            current_task_name,
            saved_search_id,
            failure_summary(exc),
        )
        raise
    finally:
        db.close()


async def _run_import(db, params: dict[str, Any]):
    filters = HHImportFilters(
        text=params["text"],
        area=str(params["area"]) if params.get("area") is not None else None,
        schedule=params.get("schedule"),
        experience=params.get("experience"),
        salary_from=params.get("salary_from"),
        salary_to=params.get("salary_to"),
        currency=params.get("currency"),
        per_page=int(params.get("per_page", 20)),
        pages_limit=int(params.get("pages_limit", 3)),
        include_details=bool(params.get("fetch_details", True)),
        extra_params=params.get("extra_params"),
    )

    async with HHClient() as hh_client:
        service = HHImportService(db=db, hh_client=hh_client)
        return await service.import_vacancies(filters)


async def _run_saved_search_sync(db, saved_search_id: int) -> dict[str, Any]:
    saved_search = db.get(SavedSearch, saved_search_id)
    if not saved_search:
        raise ValueError(f"SavedSearch not found: {saved_search_id}")

    if not saved_search.is_active:
        return {"saved_search_id": saved_search_id, "skipped": True, "reason": "inactive"}

    async with HHClient() as hh_client:
        service = HHImportService(db=db, hh_client=hh_client)
        result = await service.sync_saved_search(saved_search)

    return {
        "saved_search_id": saved_search_id,
        "saved_count": result.saved_count,
        "updated_count": result.updated_count,
        "pages_processed": result.pages_processed,
        "errors_count": result.errors_count,
        "stop_by_cutoff": result.stop_by_cutoff,
    }
