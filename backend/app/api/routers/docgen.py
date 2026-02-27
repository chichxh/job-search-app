from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.models import CoverLetterVersion, ResumeVersion
from app.db.session import get_db
from app.schemas.docgen import DocumentByTaskResponse
from app.schemas.tasks import TaskEnqueueResponse
from app.tasks.docgen_tasks import generate_cover_letter_draft_task, generate_resume_draft_task

router = APIRouter(prefix="/profiles", tags=["docgen"])


@router.post(
    "/{profile_id}/vacancies/{vacancy_id}/resume/generate",
    response_model=TaskEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_resume_draft(profile_id: int, vacancy_id: int) -> TaskEnqueueResponse:
    task = generate_resume_draft_task.apply_async(args=[profile_id, vacancy_id])
    return TaskEnqueueResponse(task_id=task.id)


@router.post(
    "/{profile_id}/vacancies/{vacancy_id}/cover-letter/generate",
    response_model=TaskEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_cover_letter_draft(profile_id: int, vacancy_id: int) -> TaskEnqueueResponse:
    task = generate_cover_letter_draft_task.apply_async(args=[profile_id, vacancy_id])
    return TaskEnqueueResponse(task_id=task.id)


@router.get("/{profile_id}/documents/by-task/{task_id}", response_model=DocumentByTaskResponse)
def get_document_by_task(profile_id: int, task_id: str, db: Session = Depends(get_db)) -> DocumentByTaskResponse:
    task_result: AsyncResult = celery_app.AsyncResult(task_id)

    if task_result.state != "SUCCESS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is not finished yet. Current state: {task_result.state}",
        )

    version_id = task_result.result
    if not isinstance(version_id, int):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task result does not contain a document version id",
        )

    resume_version = db.get(ResumeVersion, version_id)
    if resume_version and resume_version.profile_id == profile_id:
        return DocumentByTaskResponse(
            task_id=task_id,
            state=task_result.state,
            document_type="resume",
            resume_version=resume_version,
        )

    cover_letter_version = db.get(CoverLetterVersion, version_id)
    if cover_letter_version and cover_letter_version.profile_id == profile_id:
        return DocumentByTaskResponse(
            task_id=task_id,
            state=task_result.state,
            document_type="cover_letter",
            cover_letter_version=cover_letter_version,
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Generated document not found for this profile/task",
    )
