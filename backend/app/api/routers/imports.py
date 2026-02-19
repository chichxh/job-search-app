from typing import Any
from urllib.parse import parse_qs, urlparse

from celery.result import AsyncResult
from fastapi import APIRouter

from app.celery_app import celery_app
from app.integrations.hh_client import HHClient
from app.schemas.imports import HHImportRequest, HHImportTaskResponse
from app.schemas.tasks import TaskStatusResponse
from app.tasks.hh_import_tasks import import_hh_vacancies_task

router = APIRouter(tags=["imports"])


@router.post("/import/hh", response_model=HHImportTaskResponse)
def start_hh_import(payload: HHImportRequest) -> HHImportTaskResponse:
    task = import_hh_vacancies_task.apply_async(args=[payload.model_dump()])
    return HHImportTaskResponse(task_id=task.id)


@router.post("/import/hh/clusters")
async def get_hh_clusters(payload: HHImportRequest) -> dict[str, Any]:
    async with HHClient() as hh_client:
        response = await hh_client.get_vacancy_clusters(
            text=payload.text,
            area=str(payload.area) if payload.area is not None else None,
            schedule=payload.schedule,
            experience=payload.experience,
            salary=payload.salary_from,
            currency=payload.currency,
            extra_params=payload.extra_params,
        )

    normalized_clusters: list[dict[str, Any]] = []
    for cluster in response.get("clusters", []):
        cluster_copy = dict(cluster)
        cluster_items = []
        for item in cluster.get("items", []):
            item_copy = dict(item)
            raw_url = item_copy.get("url")
            if raw_url:
                parsed_params = parse_qs(urlparse(raw_url).query)
                item_copy["params"] = {
                    key: values[0] if len(values) == 1 else values
                    for key, values in parsed_params.items()
                }
            cluster_items.append(item_copy)

        cluster_copy["items"] = cluster_items
        normalized_clusters.append(cluster_copy)

    return {
        "found": response.get("found", 0),
        "clusters": normalized_clusters,
        "applied_base_params": {
            "text": payload.text,
            "area": payload.area,
            "schedule": payload.schedule,
            "experience": payload.experience,
            "salary_from": payload.salary_from,
            "salary_to": payload.salary_to,
            "currency": payload.currency,
        },
    }


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    task_result: AsyncResult = celery_app.AsyncResult(task_id)

    if task_result.state == "SUCCESS":
        return TaskStatusResponse(task_id=task_id, state=task_result.state, result=task_result.result)

    if task_result.state == "FAILURE":
        return TaskStatusResponse(task_id=task_id, state=task_result.state, error=str(task_result.result))

    return TaskStatusResponse(task_id=task_id, state=task_result.state)
