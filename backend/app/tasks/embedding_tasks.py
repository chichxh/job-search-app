import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.celery_app import celery_app
from app.db.models import Profile, ProfileEmbedding, Vacancy, VacancyEmbedding, VacancyParsed, VacancyRequirement
from app.db.session import SessionLocal
from app.services.embeddings.provider import get_embedding_provider
from app.utils.text_clean import strip_html

logger = logging.getLogger(__name__)


EMBED_BATCH_SIZE = 32


def _looks_like_html(text: str) -> bool:
    return "<" in text and ">" in text


def _build_vacancy_text(vacancy: Vacancy, key_skills: list[str], parsed_plain_text: str | None = None) -> str:
    if parsed_plain_text:
        clean_text = parsed_plain_text
    else:
        description = vacancy.description or ""
        clean_text = strip_html(description) if _looks_like_html(description) else description
    parts = [vacancy.title, clean_text]
    if key_skills:
        parts.append("Ключевые навыки: " + ", ".join(key_skills))
    return "\n\n".join(part for part in parts if part)


def _build_profile_text(profile: Profile) -> str:
    parts = [profile.title or "", profile.resume_text or "", profile.skills_text or ""]
    return "\n\n".join(part for part in parts if part)


def _upsert_vacancy_embedding(db, vacancy_id: int, vector: list[float], model_name: str) -> None:
    stmt = insert(VacancyEmbedding).values(
        vacancy_id=vacancy_id,
        embedding=vector,
        model_name=model_name,
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


def _upsert_profile_embedding(db, profile_id: int, vector: list[float], model_name: str) -> None:
    stmt = insert(ProfileEmbedding).values(
        profile_id=profile_id,
        embedding=vector,
        model_name=model_name,
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


@celery_app.task(name="app.tasks.embedding_tasks.build_vacancy_embedding")
def build_vacancy_embedding(vacancy_id: int) -> dict[str, str | int]:
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

        parsed_plain_text = db.execute(
            select(VacancyParsed.plain_text).where(VacancyParsed.vacancy_id == vacancy_id)
        ).scalar_one_or_none()

        provider = get_embedding_provider()
        text = _build_vacancy_text(vacancy, key_skills, parsed_plain_text=parsed_plain_text)
        vector = provider.embed_text(text)
        _upsert_vacancy_embedding(db, vacancy_id=vacancy_id, vector=vector, model_name=provider.name)
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
    db = SessionLocal()
    try:
        profile = db.get(Profile, profile_id)
        if not profile:
            logger.warning("Profile not found for embedding | profile_id=%s", profile_id)
            return {"status": "skipped", "reason": "profile_not_found", "profile_id": profile_id}

        provider = get_embedding_provider()
        text = _build_profile_text(profile)
        vector = provider.embed_text(text)
        _upsert_profile_embedding(db, profile_id=profile_id, vector=vector, model_name=provider.name)
        db.commit()

        return {"status": "ok", "profile_id": profile_id}
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to build profile embedding | profile_id=%s", profile_id)
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.embedding_tasks.rebuild_vacancy_embeddings")
def rebuild_vacancy_embeddings(limit: int | None = None) -> dict[str, int]:
    db = SessionLocal()
    try:
        stmt = select(Vacancy.id).order_by(Vacancy.id.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        vacancy_ids = list(db.execute(stmt).scalars().all())

        if not vacancy_ids:
            return {"status": "ok", "processed": 0}

        db.execute(delete(VacancyEmbedding).where(VacancyEmbedding.vacancy_id.in_(vacancy_ids)))

        provider = get_embedding_provider()
        for start in range(0, len(vacancy_ids), EMBED_BATCH_SIZE):
            batch_ids = vacancy_ids[start : start + EMBED_BATCH_SIZE]
            vacancies = db.execute(select(Vacancy).where(Vacancy.id.in_(batch_ids))).scalars().all()
            parsed_text_by_vacancy_id = dict(
                db.execute(select(VacancyParsed.vacancy_id, VacancyParsed.plain_text).where(VacancyParsed.vacancy_id.in_(batch_ids))).all()
            )

            texts = []
            prepared_ids = []
            for vacancy in vacancies:
                skills_stmt = select(VacancyRequirement.raw_text).where(
                    VacancyRequirement.vacancy_id == vacancy.id,
                    VacancyRequirement.kind == "skill",
                )
                key_skills = list(db.execute(skills_stmt).scalars().all())
                prepared_ids.append(vacancy.id)
                texts.append(
                    _build_vacancy_text(
                        vacancy,
                        key_skills,
                        parsed_plain_text=parsed_text_by_vacancy_id.get(vacancy.id),
                    )
                )

            vectors = provider.embed_texts(texts)
            for vacancy_id, vector in zip(prepared_ids, vectors, strict=False):
                _upsert_vacancy_embedding(db, vacancy_id=vacancy_id, vector=vector, model_name=provider.name)

        db.commit()
        return {"status": "ok", "processed": len(vacancy_ids)}
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to rebuild vacancy embeddings")
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.embedding_tasks.rebuild_profile_embeddings")
def rebuild_profile_embeddings(limit: int | None = None) -> dict[str, int]:
    db = SessionLocal()
    try:
        stmt = select(Profile.id).order_by(Profile.id.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        profile_ids = list(db.execute(stmt).scalars().all())

        if not profile_ids:
            return {"status": "ok", "processed": 0}

        db.execute(delete(ProfileEmbedding).where(ProfileEmbedding.profile_id.in_(profile_ids)))

        provider = get_embedding_provider()
        for start in range(0, len(profile_ids), EMBED_BATCH_SIZE):
            batch_ids = profile_ids[start : start + EMBED_BATCH_SIZE]
            profiles = db.execute(select(Profile).where(Profile.id.in_(batch_ids))).scalars().all()
            texts = [_build_profile_text(profile) for profile in profiles]
            vectors = provider.embed_texts(texts)
            for profile, vector in zip(profiles, vectors, strict=False):
                _upsert_profile_embedding(db, profile_id=profile.id, vector=vector, model_name=provider.name)

        db.commit()
        return {"status": "ok", "processed": len(profile_ids)}
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to rebuild profile embeddings")
        raise
    finally:
        db.close()
