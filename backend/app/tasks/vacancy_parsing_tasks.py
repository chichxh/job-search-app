import logging
from typing import Any, cast

from sqlalchemy import outerjoin, select

from app.celery_app import celery_app
from app.db.models import Vacancy, VacancyParsed
from app.db.session import SessionLocal
from app.services.hh_import_service import HHImportService
from app.services.vacancy_parsing import parse_hh_description
from app.services.vacancy_parsing.hh_parser import VERSION as HH_PARSER_VERSION
from app.tasks.embedding_tasks import build_vacancy_embedding

logger = logging.getLogger(__name__)

COMMIT_BATCH_SIZE = 100


@celery_app.task(name="app.tasks.vacancy_parsing_tasks.backfill_hh_parsed")
def backfill_hh_parsed(limit: int | None = None, only_missing: bool = True) -> dict[str, Any]:
    db = SessionLocal()
    try:
        stmt = select(Vacancy.id).where(Vacancy.source == "hh").order_by(Vacancy.id.asc())
        if only_missing:
            vacancy_parsed_join = outerjoin(Vacancy, VacancyParsed, Vacancy.id == VacancyParsed.vacancy_id)
            stmt = (
                select(Vacancy.id)
                .select_from(vacancy_parsed_join)
                .where(Vacancy.source == "hh")
                .where((VacancyParsed.vacancy_id.is_(None)) | (VacancyParsed.version != HH_PARSER_VERSION))
                .order_by(Vacancy.id.asc())
            )
        if limit is not None:
            stmt = stmt.limit(limit)

        vacancy_ids = list(db.execute(stmt).scalars().all())
        if not vacancy_ids:
            return {"status": "ok", "processed": 0, "enqueued_embeddings": 0}

        hh_import_service = HHImportService(db=db, hh_client=cast(Any, None))
        processed = 0
        errors = 0
        enqueued_embeddings = 0
        batch_embedding_ids: list[int] = []

        for vacancy_id in vacancy_ids:
            vacancy = db.get(Vacancy, vacancy_id)
            if vacancy is None:
                continue

            try:
                parsed = parse_hh_description(vacancy.description or "")
                hh_import_service._upsert_vacancy_parsed(vacancy_id, parsed)
                hh_import_service._replace_generated_requirements(vacancy_id, details=None, parsed=parsed)
                processed += 1
                batch_embedding_ids.append(vacancy_id)
            except Exception:  # noqa: BLE001
                db.rollback()
                errors += 1
                logger.exception("Failed to backfill HH parsed vacancy | vacancy_id=%s", vacancy_id)
                continue

            if len(batch_embedding_ids) >= COMMIT_BATCH_SIZE:
                db.commit()
                for batch_vacancy_id in batch_embedding_ids:
                    build_vacancy_embedding.delay(batch_vacancy_id)
                    enqueued_embeddings += 1
                batch_embedding_ids = []

        db.commit()
        for batch_vacancy_id in batch_embedding_ids:
            build_vacancy_embedding.delay(batch_vacancy_id)
            enqueued_embeddings += 1

        return {
            "status": "ok",
            "processed": processed,
            "errors": errors,
            "enqueued_embeddings": enqueued_embeddings,
            "targeted": len(vacancy_ids),
            "only_missing": only_missing,
            "limit": limit,
            "version": HH_PARSER_VERSION,
        }
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to backfill HH parsed vacancies")
        raise
    finally:
        db.close()
