import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.matching.matching_service import MatchingService

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.matching_tasks.compute_profile_recommendations")
def compute_profile_recommendations(profile_id: int, limit: int = 50) -> dict:
    """Recompute recommendations for a profile in the background."""

    db = SessionLocal()
    try:
        service = MatchingService(db)
        scores = service.compute_recommendations(profile_id=profile_id, limit=limit)

        return {
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
    except ValueError as exc:
        logger.warning(
            "Recommendations task skipped | profile_id=%s limit=%s reason=%s",
            profile_id,
            limit,
            exc,
        )
        return {
            "profile_id": profile_id,
            "computed": 0,
            "top": [],
        }
    except Exception:  # noqa: BLE001
        logger.exception("Recommendations task failed | profile_id=%s limit=%s", profile_id, limit)
        raise
    finally:
        db.close()
