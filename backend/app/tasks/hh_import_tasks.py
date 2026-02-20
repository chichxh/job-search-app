import asyncio
import logging
from typing import Any

from sqlalchemy import select

from app.celery_app import celery_app
from app.db.models import SavedSearch
from app.db.session import SessionLocal
from app.integrations.hh_client import HHClient
from app.services.hh_import_service import HHImportFilters, HHImportService

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.hh_import_tasks.import_hh_vacancies_task")
def import_hh_vacancies_task(params: dict[str, Any]) -> dict[str, int]:
    """Import vacancies from HH and store them in Postgres."""

    logger.info("HH celery task started | params=%s", params)
    db = SessionLocal()
    try:
        result = asyncio.run(_run_import(db, params))
        payload = {
            "saved_count": result.saved_count,
            "updated_count": result.updated_count,
            "pages_processed": result.pages_processed,
            "errors_count": result.errors_count,
        }
        logger.info("HH celery task finished | result=%s", payload)
        return payload
    except Exception:  # noqa: BLE001
        logger.exception("HH celery task failed | params=%s", params)
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.hh_import_tasks.schedule_saved_search_sync")
def schedule_saved_search_sync() -> dict[str, int]:
    """Beat task that enqueues sync jobs for all active saved searches."""

    db = SessionLocal()
    try:
        stmt = select(SavedSearch.id).where(SavedSearch.is_active.is_(True))
        saved_search_ids = list(db.execute(stmt).scalars().all())

        for search_id in saved_search_ids:
            sync_saved_search_task.delay(search_id)

        logger.info("Enqueued saved search sync tasks | active_searches=%s", len(saved_search_ids))
        return {"enqueued": len(saved_search_ids)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.hh_import_tasks.sync_saved_search_task")
def sync_saved_search_task(saved_search_id: int) -> dict[str, Any]:
    """Sync a single SavedSearch with HH and update sync markers."""

    logger.info("Saved search sync started | saved_search_id=%s", saved_search_id)
    db = SessionLocal()
    try:
        payload = asyncio.run(_run_saved_search_sync(db, saved_search_id))
        logger.info("Saved search sync finished | payload=%s", payload)
        return payload
    except Exception:  # noqa: BLE001
        logger.exception("Saved search sync failed | saved_search_id=%s", saved_search_id)
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
