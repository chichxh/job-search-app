from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import Profile, ProfileEmbedding, Vacancy, VacancyEmbedding
from app.db.session import get_db
from app.tasks.embedding_tasks import build_profile_embedding, build_vacancy_embedding

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
