import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.celery_app import celery_app
from app.db.models import Profile, ProfileEmbedding, Vacancy, VacancyEmbedding, VacancyRequirement
from app.db.session import SessionLocal
from app.services.embeddings.provider import get_embedding_provider
from app.utils.text_clean import strip_html

logger = logging.getLogger(__name__)


def _looks_like_html(text: str) -> bool:
    return "<" in text and ">" in text


def _build_vacancy_text(vacancy: Vacancy, key_skills: list[str]) -> str:
    # Собираем единый текст для embedding.
    description = vacancy.description or ""
    clean_text = strip_html(description) if _looks_like_html(description) else description
    parts = [vacancy.title, clean_text]
    if key_skills:
        parts.append("Ключевые навыки: " + ", ".join(key_skills))
    return "\n\n".join(part for part in parts if part)


def _build_profile_text(profile: Profile) -> str:
    # Собираем единый текст профиля.
    parts = [profile.title or "", profile.resume_text or "", profile.skills_text or ""]
    return "\n\n".join(part for part in parts if part)


@celery_app.task(name="app.tasks.embedding_tasks.build_vacancy_embedding")
def build_vacancy_embedding(vacancy_id: int) -> dict[str, str | int]:
    """Считает и сохраняет embedding вакансии."""

    db = SessionLocal()
    try:
        vacancy = db.get(Vacancy, vacancy_id)
        if not vacancy:
            logger.warning("Vacancy not found for embedding | vacancy_id=%s", vacancy_id)
            return {"status": "skipped", "reason": "vacancy_not_found", "vacancy_id": vacancy_id}

        skills_stmt = select(VacancyRequirement.raw_text).where(
            VacancyRequirement.vacancy_id == vacancy_id,
            VacancyRequirement.kind == "skill",
        )
        key_skills = list(db.execute(skills_stmt).scalars().all())

        provider = get_embedding_provider()
        text = _build_vacancy_text(vacancy, key_skills)
        vector = provider.embed_text(text)

        stmt = insert(VacancyEmbedding).values(
            vacancy_id=vacancy_id,
            embedding=vector,
            model_name=provider.name,
            updated_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[VacancyEmbedding.vacancy_id],
            set_={
                "embedding": stmt.excluded.embedding,
                "model_name": stmt.excluded.model_name,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db.execute(stmt)
        db.commit()

        return {"status": "ok", "vacancy_id": vacancy_id}
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to build vacancy embedding | vacancy_id=%s", vacancy_id)
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.embedding_tasks.build_profile_embedding")
def build_profile_embedding(profile_id: int) -> dict[str, str | int]:
    """Считает и сохраняет embedding профиля."""

    db = SessionLocal()
    try:
        profile = db.get(Profile, profile_id)
        if not profile:
            logger.warning("Profile not found for embedding | profile_id=%s", profile_id)
            return {"status": "skipped", "reason": "profile_not_found", "profile_id": profile_id}

        provider = get_embedding_provider()
        text = _build_profile_text(profile)
        vector = provider.embed_text(text)

        stmt = insert(ProfileEmbedding).values(
            profile_id=profile_id,
            embedding=vector,
            model_name=provider.name,
            updated_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProfileEmbedding.profile_id],
            set_={
                "embedding": stmt.excluded.embedding,
                "model_name": stmt.excluded.model_name,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db.execute(stmt)
        db.commit()

        return {"status": "ok", "profile_id": profile_id}
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to build profile embedding | profile_id=%s", profile_id)
        raise
    finally:
        db.close()
