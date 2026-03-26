from celery import chain
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import Profile
from app.db.session import get_db
from app.schemas.tasks import RecomputeAllTasksResponse, TaskEnqueueResponse
from app.services.matching.diagnostics_service import MatchingDiagnosticsService, merge_quality_diagnostics
from app.tasks.embedding_tasks import build_profile_embedding
from app.tasks.matching_tasks import compute_profile_recommendations
from app.tasks.profile_backfill_tasks import backfill_profile

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/profiles/{profile_id}/backfill", response_model=TaskEnqueueResponse)
def start_profile_backfill(profile_id: int) -> TaskEnqueueResponse:
    task = backfill_profile.apply_async(args=[profile_id])
    return TaskEnqueueResponse(task_id=task.id)


@router.post("/profiles/{profile_id}/recompute-all", response_model=RecomputeAllTasksResponse)
def recompute_profile_all(
    profile_id: int,
    limit: int = Query(default=100, ge=1, le=500),
) -> RecomputeAllTasksResponse:
    workflow = chain(
        backfill_profile.si(profile_id),
        build_profile_embedding.si(profile_id),
        compute_profile_recommendations.si(profile_id, limit),
    )

    task = workflow.apply_async()

    recommendation_task_id = task.id
    embedding_task_id = task.parent.id if task.parent else ""
    backfill_task_id = task.parent.parent.id if task.parent and task.parent.parent else ""

    return RecomputeAllTasksResponse(
        task_ids={
            "backfill_profile": backfill_task_id,
            "rebuild_profile_embedding": embedding_task_id,
            "compute_profile_recommendations": recommendation_task_id,
        }
    )


@router.get("/matching/diagnostics")
def get_matching_diagnostics(
    low_quality_threshold: float = Query(default=0.45, ge=0.0, le=1.0),
    profile_id: int | None = Query(default=None),
    top_n: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    service = MatchingDiagnosticsService(db)
    global_summary = service.build_global_summary(low_quality_threshold=low_quality_threshold)

    if profile_id is None:
        return {"global": global_summary}

    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    profile_summary = service.build_profile_summary(profile_id=profile_id, top_n=top_n)
    return merge_quality_diagnostics(global_summary, profile_summary)


@router.get("/profiles/{profile_id}/matching/diagnostics")
def get_profile_matching_diagnostics(
    profile_id: int,
    top_n: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    service = MatchingDiagnosticsService(db)
    return service.build_profile_summary(profile_id=profile_id, top_n=top_n)
