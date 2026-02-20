from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Vacancy, VacancyEmbedding
from app.db.session import get_db
from app.tasks.embedding_tasks import build_vacancy_embedding

router = APIRouter(tags=["embeddings"])


@router.post("/dev/embeddings/rebuild-vacancies")
def rebuild_vacancy_embeddings(
    limit: int = Query(default=10, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict[str, int | list[int]]:
    # Берем последние N вакансий и ставим задачи в очередь.
    vacancy_ids = list(
        db.execute(select(Vacancy.id).order_by(Vacancy.id.desc()).limit(limit)).scalars().all()
    )

    for vacancy_id in vacancy_ids:
        build_vacancy_embedding.delay(vacancy_id)

    if vacancy_ids:
        emb_count = int(
            db.execute(
                select(func.count())
                .select_from(VacancyEmbedding)
                .where(VacancyEmbedding.vacancy_id.in_(vacancy_ids))
            ).scalar_one()
        )
    else:
        emb_count = 0

    return {
        "enqueued": len(vacancy_ids),
        "vacancy_ids": vacancy_ids,
        "current_embeddings_for_selected": emb_count,
    }
