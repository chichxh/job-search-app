import logging
from time import perf_counter

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.matching.matching_service import MatchingService
from app.tasks.observability import failure_summary, mark_task_started, success_meta, task_name

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.matching_tasks.compute_profile_recommendations")
def compute_profile_recommendations(self, profile_id: int, limit: int = 50) -> dict:
    """Recompute recommendations for a profile in the background."""
    current_task_name = task_name(self, "compute_profile_recommendations")
    timer_started = perf_counter()
    started_at = mark_task_started(
        self,
        name=current_task_name,
        message="Recommendations recompute in progress",
        extra={"flow": "recommendations_recompute", "profile_id": profile_id, "limit": limit},
    )
    logger.info("Task started | task=%s profile_id=%s limit=%s", current_task_name, profile_id, limit)
    db = SessionLocal()
    try:
        service = MatchingService(db)
        scores = service.compute_recommendations(profile_id=profile_id, limit=limit)

        payload = {
            "profile_id": profile_id,
            "computed": len(scores),
            "top": [
                {
                    "vacancy_id": score.vacancy_id,
                    "final_score": score.final_score,
                    "verdict": score.verdict,
                }
                for score in scores[:5]
            ],
        }
        payload.update(
            success_meta(
                current_task_name,
                started_at=started_at,
                timer_started=timer_started,
                message="Recommendations recompute finished",
            )
        )
        logger.info("Task finished | task=%s profile_id=%s computed=%s", current_task_name, profile_id, len(scores))
        return payload
    except ValueError as exc:
        logger.warning(
            "Task skipped | task=%s profile_id=%s limit=%s reason=%s",
            current_task_name,
            profile_id,
            limit,
            exc,
        )
        return {
            "profile_id": profile_id,
            "computed": 0,
            "top": [],
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Task failed | task=%s profile_id=%s limit=%s summary=%s",
            current_task_name,
            profile_id,
            limit,
            failure_summary(exc),
        )
        raise
    finally:
        db.close()
