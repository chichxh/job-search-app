from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import SavedSearch
from app.db.session import get_db
from app.integrations.hh_client import HHClient
from app.schemas.saved_searches import (
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchSyncResponse,
    SavedSearchUpdate,
)
from app.tasks.hh_import_tasks import sync_saved_search_task

router = APIRouter(tags=["saved_searches"])


@router.post("/saved-searches", response_model=SavedSearchResponse)
def create_saved_search(payload: SavedSearchCreate, db: Session = Depends(get_db)) -> SavedSearch:
    saved_search = SavedSearch(**payload.model_dump())
    db.add(saved_search)
    db.commit()
    db.refresh(saved_search)
    return saved_search


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
def list_saved_searches(db: Session = Depends(get_db)) -> list[SavedSearch]:
    return db.query(SavedSearch).order_by(SavedSearch.id.desc()).all()


@router.patch("/saved-searches/{saved_search_id}", response_model=SavedSearchResponse)
def update_saved_search(
    saved_search_id: int,
    payload: SavedSearchUpdate,
    db: Session = Depends(get_db),
) -> SavedSearch:
    saved_search = db.get(SavedSearch, saved_search_id)
    if not saved_search:
        raise HTTPException(status_code=404, detail="Saved search not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(saved_search, field, value)

    db.add(saved_search)
    db.commit()
    db.refresh(saved_search)
    return saved_search


@router.post("/saved-searches/{saved_search_id}/sync", response_model=SavedSearchSyncResponse)
def sync_saved_search(saved_search_id: int, db: Session = Depends(get_db)) -> SavedSearchSyncResponse:
    saved_search = db.get(SavedSearch, saved_search_id)
    if not saved_search:
        raise HTTPException(status_code=404, detail="Saved search not found")

    task = sync_saved_search_task.delay(saved_search_id)
    return SavedSearchSyncResponse(task_id=task.id)


@router.get("/saved-searches/{saved_search_id}/clusters")
async def get_saved_search_clusters(saved_search_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    saved_search = db.get(SavedSearch, saved_search_id)
    if not saved_search:
        raise HTTPException(status_code=404, detail="Saved search not found")

    async with HHClient() as hh_client:
        response = await hh_client.get_vacancy_clusters(
            text=saved_search.text,
            area=saved_search.area,
            schedule=saved_search.schedule,
            experience=saved_search.experience,
            salary=saved_search.salary_from,
            currency=saved_search.currency,
            extra_params=saved_search.filters_json,
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
        "saved_search_id": saved_search.id,
        "found": response.get("found", 0),
        "clusters": normalized_clusters,
        "applied_base_params": {
            "text": saved_search.text,
            "area": saved_search.area,
            "schedule": saved_search.schedule,
            "experience": saved_search.experience,
            "salary_from": saved_search.salary_from,
            "salary_to": saved_search.salary_to,
            "currency": saved_search.currency,
            "filters_json": saved_search.filters_json,
        },
    }
