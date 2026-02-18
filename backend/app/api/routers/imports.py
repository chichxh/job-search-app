from celery.result import AsyncResult
from fastapi import APIRouter

from app.celery_app import celery_app
from app.schemas.imports import HHImportRequest, HHImportTaskResponse
from app.schemas.tasks import TaskStatusResponse
from app.tasks.hh_import_tasks import import_hh_vacancies_task

router = APIRouter(tags=["imports"])


@router.post("/import/hh", response_model=HHImportTaskResponse)
def start_hh_import(payload: HHImportRequest) -> HHImportTaskResponse:
    task = import_hh_vacancies_task.apply_async(args=[payload.model_dump()])
    return HHImportTaskResponse(task_id=task.id)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    task_result: AsyncResult = celery_app.AsyncResult(task_id)

    if task_result.state == "SUCCESS":
        return TaskStatusResponse(task_id=task_id, state=task_result.state, result=task_result.result)

    if task_result.state == "FAILURE":
        return TaskStatusResponse(task_id=task_id, state=task_result.state, error=str(task_result.result))

    return TaskStatusResponse(task_id=task_id, state=task_result.state)
