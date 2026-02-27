from fastapi import APIRouter

from app.schemas.tasks import TaskEnqueueResponse
from app.tasks.profile_backfill_tasks import backfill_profile

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/profiles/{profile_id}/backfill", response_model=TaskEnqueueResponse)
def start_profile_backfill(profile_id: int) -> TaskEnqueueResponse:
    task = backfill_profile.apply_async(args=[profile_id])
    return TaskEnqueueResponse(task_id=task.id)
