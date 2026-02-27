import logging
from typing import Any, cast

from sqlalchemy import outerjoin, select

from app.celery_app import celery_app
from app.db.models import Vacancy, VacancyParsed
from app.db.session import SessionLocal
from app.services.hh_import_service import HHImportService
from app.services.requirements_extractor import extract_requirements_from_sections
from app.services.vacancy_parsing import parse_hh_description
from app.services.vacancy_parsing.hh_parser import VERSION as HH_PARSER_VERSION
from app.tasks.embedding_tasks import rebuild_vacancy_embeddings_for_ids

logger = logging.getLogger(__name__)

COMMIT_BATCH_SIZE = 100
EMBEDDING_BATCH_SIZE = 256
RECOMMENDATION_PROFILES = (1, 2)


@celery_app.task(name="app.tasks.vacancy_parsing_tasks.backfill_hh_parsed")
def backfill_hh_parsed(
    limit: int | None = None,
    only_missing: bool = True,
    schedule_embeddings: bool = True,
    schedule_recommendations: bool = True,
    embedding_batch_size: int = EMBEDDING_BATCH_SIZE,
    recommendations_limit: int = 50,
) -> dict[str, Any]:
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
            return {
                "status": "ok",
                "processed": 0,
                "errors": 0,
                "enqueued_embedding_tasks": 0,
                "enqueued_embeddings": 0,
                "enqueued_recommendations": 0,
            }

        hh_import_service = HHImportService(db=db, hh_client=cast(Any, None))
        processed = 0
        errors = 0
        processed_vacancy_ids: list[int] = []

        for vacancy_id in vacancy_ids:
            vacancy = db.get(Vacancy, vacancy_id)
            if vacancy is None:
                continue

            try:
                parsed = parse_hh_description(vacancy.description or "")
                section_requirements = extract_requirements_from_sections(parsed.get("sections") or {})
                hh_import_service._upsert_vacancy_parsed(vacancy_id, parsed)
                hh_import_service._replace_generated_requirements(
                    vacancy_id,
                    details=None,
                    parsed=parsed,
                    section_requirements=section_requirements,
                )
                processed += 1
                processed_vacancy_ids.append(vacancy_id)
            except Exception:  # noqa: BLE001
                db.rollback()
                errors += 1
                logger.exception("Failed to backfill HH parsed vacancy | vacancy_id=%s", vacancy_id)
                continue

            if processed % COMMIT_BATCH_SIZE == 0:
                db.commit()

        db.commit()

        enqueued_embedding_tasks = 0
        enqueued_embeddings = 0
        if schedule_embeddings and processed_vacancy_ids:
            batch_size = max(1, embedding_batch_size)
            for start in range(0, len(processed_vacancy_ids), batch_size):
                batch_ids = processed_vacancy_ids[start : start + batch_size]
                rebuild_vacancy_embeddings_for_ids.delay(batch_ids)
                enqueued_embedding_tasks += 1
                enqueued_embeddings += len(batch_ids)

        enqueued_recommendations = 0
        if schedule_recommendations:
            try:
                from app.tasks.matching_tasks import compute_profile_recommendations

                for profile_id in RECOMMENDATION_PROFILES:
                    compute_profile_recommendations.delay(profile_id, recommendations_limit)
                    enqueued_recommendations += 1
            except Exception:  # noqa: BLE001
                logger.exception("Failed to enqueue profile recommendations recompute")

        return {
            "status": "ok",
            "processed": processed,
            "errors": errors,
            "enqueued_embedding_tasks": enqueued_embedding_tasks,
            "enqueued_embeddings": enqueued_embeddings,
            "enqueued_recommendations": enqueued_recommendations,
            "targeted": len(vacancy_ids),
            "only_missing": only_missing,
            "limit": limit,
            "version": HH_PARSER_VERSION,
            "schedule_embeddings": schedule_embeddings,
            "schedule_recommendations": schedule_recommendations,
            "embedding_batch_size": max(1, embedding_batch_size),
            "recommendations_limit": recommendations_limit,
        }
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to backfill HH parsed vacancies")
        raise
    finally:
        db.close()
