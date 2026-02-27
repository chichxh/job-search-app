from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import Profile, ProfileEmbedding, Vacancy, VacancyEmbedding
from app.db.session import get_db
from app.tasks.embedding_tasks import build_profile_embedding, build_vacancy_embedding
from app.tasks.vacancy_parsing_tasks import backfill_hh_parsed

router = APIRouter(tags=["embeddings"])


@router.post("/dev/embeddings/rebuild-vacancies")
def rebuild_vacancy_embeddings(
    limit: int = Query(default=10, ge=1, le=100000),
    db: Session = Depends(get_db),
) -> dict[str, int | list[int]]:
    vacancy_ids = list(db.execute(select(Vacancy.id).order_by(Vacancy.id.desc()).limit(limit)).scalars().all())

    if vacancy_ids:
        db.execute(delete(VacancyEmbedding).where(VacancyEmbedding.vacancy_id.in_(vacancy_ids)))
        db.commit()

    for vacancy_id in vacancy_ids:
        build_vacancy_embedding.delay(vacancy_id)

    emb_count = 0
    if vacancy_ids:
        emb_count = int(
            db.execute(
                select(func.count())
                .select_from(VacancyEmbedding)
                .where(VacancyEmbedding.vacancy_id.in_(vacancy_ids))
            ).scalar_one()
        )

    return {
        "enqueued": len(vacancy_ids),
        "vacancy_ids": vacancy_ids,
        "current_embeddings_for_selected": emb_count,
    }


@router.post("/dev/embeddings/rebuild-profiles")
def rebuild_profile_embeddings(
    limit: int = Query(default=10, ge=1, le=100000),
    db: Session = Depends(get_db),
) -> dict[str, int | list[int]]:
    profile_ids = list(db.execute(select(Profile.id).order_by(Profile.id.desc()).limit(limit)).scalars().all())

    if profile_ids:
        db.execute(delete(ProfileEmbedding).where(ProfileEmbedding.profile_id.in_(profile_ids)))
        db.commit()

    for profile_id in profile_ids:
        build_profile_embedding.delay(profile_id)

    emb_count = 0
    if profile_ids:
        emb_count = int(
            db.execute(
                select(func.count())
                .select_from(ProfileEmbedding)
                .where(ProfileEmbedding.profile_id.in_(profile_ids))
            ).scalar_one()
        )

    return {
        "enqueued": len(profile_ids),
        "profile_ids": profile_ids,
        "current_embeddings_for_selected": emb_count,
    }


@router.post("/dev/embeddings/rebuild-profile/{profile_id}")
def rebuild_single_profile_embedding(
    profile_id: int,
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    profile = db.get(Profile, profile_id)
    if profile is None:
        return {"status": "skipped", "reason": "profile_not_found", "profile_id": profile_id}

    db.execute(delete(ProfileEmbedding).where(ProfileEmbedding.profile_id == profile_id))
    db.commit()

    build_profile_embedding.delay(profile_id)
    return {"status": "enqueued", "profile_id": profile_id}


@router.post("/dev/vacancies/hh/backfill-parsed")
def backfill_hh_vacancies_parsed(
    limit: int | None = Query(default=None, ge=1, le=100000),
    only_missing: bool = Query(default=True),
    schedule_embeddings: bool = Query(default=True),
    schedule_recommendations: bool = Query(default=True),
    embedding_batch_size: int = Query(default=256, ge=1, le=5000),
    recommendations_limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, str | int | bool | None]:
    task = backfill_hh_parsed.delay(
        limit=limit,
        only_missing=only_missing,
        schedule_embeddings=schedule_embeddings,
        schedule_recommendations=schedule_recommendations,
        embedding_batch_size=embedding_batch_size,
        recommendations_limit=recommendations_limit,
    )
    return {
        "status": "enqueued",
        "task_id": task.id,
        "limit": limit,
        "only_missing": only_missing,
        "schedule_embeddings": schedule_embeddings,
        "schedule_recommendations": schedule_recommendations,
        "embedding_batch_size": embedding_batch_size,
        "recommendations_limit": recommendations_limit,
    }
