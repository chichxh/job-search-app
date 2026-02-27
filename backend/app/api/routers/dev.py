from celery import chain
from fastapi import APIRouter, Query

from app.schemas.tasks import RecomputeAllTasksResponse, TaskEnqueueResponse
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
