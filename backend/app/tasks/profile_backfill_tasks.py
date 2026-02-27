from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.celery_app import celery_app
from app.db.models import Profile, ProfileSkill, ResumeVersion
from app.db.session import SessionLocal
from app.services.matching.utils import normalize_skill

_SKILLS_SPLIT_RE = re.compile(r"[;,]")


@celery_app.task(name="app.tasks.profile_backfill_tasks.backfill_profile")
def backfill_profile(profile_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        profile = db.get(Profile, profile_id)
        if profile is None:
            return {"status": "not_found", "profile_id": profile_id}

        created_resume_version = False
        created_skills = 0

        has_resume_versions = db.execute(
            select(ResumeVersion.id).where(ResumeVersion.profile_id == profile_id).limit(1)
        ).scalar_one_or_none()
        if has_resume_versions is None:
            resume_version = ResumeVersion(
                profile_id=profile_id,
                vacancy_id=None,
                content_text=profile.resume_text,
                source="legacy_import",
                status="approved",
                approved_at=datetime.now(timezone.utc),
            )
            db.add(resume_version)
            created_resume_version = True

        has_profile_skills = db.execute(
            select(ProfileSkill.id).where(ProfileSkill.profile_id == profile_id).limit(1)
        ).scalar_one_or_none()
        if (profile.skills_text or "").strip() and has_profile_skills is None:
            skill_candidates = [
                raw_skill.strip() for raw_skill in _SKILLS_SPLIT_RE.split(profile.skills_text or "") if raw_skill.strip()
            ]
            seen: set[str] = set()

            for raw_skill in skill_candidates:
                normalized_key = normalize_skill(raw_skill)
                if not normalized_key or normalized_key in seen:
                    continue

                seen.add(normalized_key)
                db.add(
                    ProfileSkill(
                        profile_id=profile_id,
                        name_raw=raw_skill,
                        normalized_key=normalized_key,
                        category="technical",
                        level="unspecified",
                        is_primary=False,
                    )
                )
                created_skills += 1

        db.commit()

        return {
            "status": "ok",
            "profile_id": profile_id,
            "created_resume_version": created_resume_version,
            "created_skills": created_skills,
        }
    except Exception:  # noqa: BLE001
        db.rollback()
        raise
    finally:
        db.close()
