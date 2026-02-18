import asyncio
import logging
from typing import Any

from app.celery_app import celery_app
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


async def _run_import(db, params: dict[str, Any]):
    filters = HHImportFilters(
        text=params["text"],
        area=str(params["area"]) if params.get("area") is not None else None,
        per_page=int(params.get("per_page", 20)),
        pages_limit=int(params.get("pages_limit", 3)),
        include_details=bool(params.get("fetch_details", True)),
    )

    async with HHClient() as hh_client:
        service = HHImportService(db=db, hh_client=hh_client)
        return await service.import_vacancies(filters)
