import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.docgen.document_generation_service import DocumentGenerationService

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.docgen_tasks.generate_resume_draft_task")
def generate_resume_draft_task(profile_id: int, vacancy_id: int) -> int:
    db = SessionLocal()
    try:
        service = DocumentGenerationService(db)
        draft = service.generate_resume_draft(profile_id=profile_id, vacancy_id=vacancy_id)
        db.commit()
        return draft.id
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception(
            "Resume generation task failed | profile_id=%s vacancy_id=%s",
            profile_id,
            vacancy_id,
        )
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.docgen_tasks.generate_cover_letter_draft_task")
def generate_cover_letter_draft_task(profile_id: int, vacancy_id: int) -> int:
    db = SessionLocal()
    try:
        service = DocumentGenerationService(db)
        draft = service.generate_cover_letter_draft(profile_id=profile_id, vacancy_id=vacancy_id)
        db.commit()
        return draft.id
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception(
            "Cover letter generation task failed | profile_id=%s vacancy_id=%s",
            profile_id,
            vacancy_id,
        )
        raise
    finally:
        db.close()
