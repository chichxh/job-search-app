from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_llm_settings
from app.db.models import (
    CoverLetterVersion,
    Profile,
    ProfileAchievement,
    ProfileExperience,
    ProfileProject,
    ProfileSkill,
    ResumeEvidence,
    ResumeVersion,
    Vacancy,
    VacancyParsed,
    VacancyScore,
)
from app.llm import LLMMessage, LLMRequest, get_llm_client
from app.services.docgen.prompt_builders import build_cover_letter_prompt, build_resume_prompt
from app.services.matching.matching_service import MatchingService


class DocumentGenerationService:
    def __init__(self, db: Session):
        self.db = db

    def generate_resume_draft(self, profile_id: int, vacancy_id: int | None) -> ResumeVersion:
        profile_facts = self._collect_profile_facts(profile_id)
        vacancy_facts = self._collect_vacancy_facts(vacancy_id) if vacancy_id is not None else {}
        tailoring = self._collect_tailoring(profile_id=profile_id, vacancy_id=vacancy_id)

        messages = build_resume_prompt(profile_facts, vacancy_facts, tailoring)
        response = self._generate_llm_response(messages)

        metadata = self._build_generation_metadata(
            profile_facts=profile_facts,
            vacancy_facts=vacancy_facts,
            tailoring=tailoring,
            provider=response.provider,
            model=response.model,
        )

        draft = ResumeVersion(
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            content_text=response.text,
            source="ai",
            status="draft",
            title=self._build_title("AI resume draft", metadata),
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def generate_cover_letter_draft(self, profile_id: int, vacancy_id: int) -> CoverLetterVersion:
        profile_facts = self._collect_profile_facts(profile_id)
        vacancy_facts = self._collect_vacancy_facts(vacancy_id)
        tailoring = self._collect_tailoring(profile_id=profile_id, vacancy_id=vacancy_id)

        messages = build_cover_letter_prompt(profile_facts, vacancy_facts, tailoring)
        response = self._generate_llm_response(messages)

        metadata = self._build_generation_metadata(
            profile_facts=profile_facts,
            vacancy_facts=vacancy_facts,
            tailoring=tailoring,
            provider=response.provider,
            model=response.model,
        )

        draft = CoverLetterVersion(
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            content_text=response.text,
            source="ai",
            status="draft",
            title=self._build_title("AI cover letter draft", metadata),
            subject="Сопроводительное письмо",
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def _generate_llm_response(self, messages: list[LLMMessage]):
        settings = get_llm_settings()
        client = get_llm_client()
        return client.generate(
            LLMRequest(
                messages=messages,
                model=settings.model,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
            )
        )

    def _collect_profile_facts(self, profile_id: int) -> dict[str, Any]:
        profile = self.db.get(Profile, profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        skills = self.db.execute(
            select(ProfileSkill)
            .where(ProfileSkill.profile_id == profile_id)
            .order_by(ProfileSkill.is_primary.desc(), ProfileSkill.years.desc().nullslast(), ProfileSkill.id.desc())
        ).scalars().all()

        experiences = self.db.execute(
            select(ProfileExperience)
            .where(ProfileExperience.profile_id == profile_id)
            .order_by(
                ProfileExperience.start_date.desc(),
                ProfileExperience.end_date.desc().nullslast(),
                ProfileExperience.id.desc(),
            )
            .limit(5)
        ).scalars().all()

        projects = self.db.execute(
            select(ProfileProject)
            .where(ProfileProject.profile_id == profile_id)
            .order_by(
                ProfileProject.start_date.desc().nullslast(),
                ProfileProject.created_at.desc(),
                ProfileProject.id.desc(),
            )
            .limit(5)
        ).scalars().all()

        achievements = self.db.execute(
            select(ProfileAchievement)
            .where(ProfileAchievement.profile_id == profile_id)
            .order_by(ProfileAchievement.achieved_at.desc().nullslast(), ProfileAchievement.id.desc())
            .limit(5)
        ).scalars().all()

        return {
            "full_name": profile.full_name,
            "headline": profile.title,
            "summary_about": profile.summary_about,
            "city": profile.city,
            "remote_ok": profile.remote_ok,
            "relocation_ok": profile.relocation_ok,
            "skills": [
                {
                    "name": item.name_raw,
                    "level": item.level,
                    "years": item.years,
                }
                for item in skills
            ],
            "experiences": [
                {
                    "company_name": item.company_name,
                    "position_title": item.position_title,
                    "start_date": item.start_date.isoformat() if item.start_date else None,
                    "end_date": item.end_date.isoformat() if item.end_date else None,
                    "is_current": item.is_current,
                    "responsibilities": item.responsibilities_text,
                    "achievements": item.achievements_text,
                    "tech_stack": item.tech_stack_text,
                }
                for item in experiences
            ],
            "projects": [
                {
                    "name": item.name,
                    "role": item.role,
                    "description": item.description_text,
                    "tech_stack": item.tech_stack_text,
                    "url": item.url,
                }
                for item in projects
            ],
            "achievements": [
                {
                    "title": item.title,
                    "description": item.description_text,
                    "metric": item.metric,
                }
                for item in achievements
            ],
        }

    def _collect_vacancy_facts(self, vacancy_id: int) -> dict[str, Any]:
        vacancy = self.db.get(Vacancy, vacancy_id)
        if not vacancy:
            raise ValueError(f"Vacancy not found: {vacancy_id}")

        parsed = self.db.get(VacancyParsed, vacancy_id)

        return {
            "vacancy_id": vacancy.id,
            "title": vacancy.title,
            "company_name": vacancy.company_name,
            "location": vacancy.location,
            "description": vacancy.description,
            "plain_text": parsed.plain_text if parsed else None,
            "sections_json": parsed.sections_json if parsed else {},
        }

    def _collect_tailoring(self, profile_id: int, vacancy_id: int | None) -> dict[str, Any]:
        if vacancy_id is None:
            return {}

        matching_service = MatchingService(self.db)
        if hasattr(matching_service, "get_tailoring"):
            try:
                tailoring = matching_service.get_tailoring(profile_id=profile_id, vacancy_id=vacancy_id)
                if isinstance(tailoring, dict):
                    return tailoring
            except Exception:
                pass

        score = self.db.execute(
            select(VacancyScore.explanation).where(
                VacancyScore.profile_id == profile_id,
                VacancyScore.vacancy_id == vacancy_id,
            )
        ).scalar_one_or_none()

        evidence = self.db.execute(
            select(ResumeEvidence.evidence_text, ResumeEvidence.confidence)
            .where(
                ResumeEvidence.profile_id == profile_id,
                ResumeEvidence.vacancy_id == vacancy_id,
            )
            .order_by(ResumeEvidence.confidence.desc(), ResumeEvidence.id.desc())
        ).all()

        return {
            "explanation": score or {},
            "evidence": [{"text": row.evidence_text, "confidence": row.confidence} for row in evidence],
        }

    def _build_generation_metadata(
        self,
        *,
        profile_facts: dict[str, Any],
        vacancy_facts: dict[str, Any],
        tailoring: dict[str, Any],
        provider: str,
        model: str | None,
    ) -> dict[str, str]:
        payload = {
            "profile_facts": profile_facts,
            "vacancy_facts": vacancy_facts,
            "tailoring": tailoring,
        }
        input_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        return {
            "provider": provider,
            "model": model or "",
            "prompt_version": "v1",
            "input_hash": input_hash,
        }

    @staticmethod
    def _build_title(prefix: str, metadata: dict[str, str]) -> str:
        short_hash = metadata["input_hash"][:12]
        model = metadata.get("model") or "unknown-model"
        provider = metadata.get("provider") or "unknown-provider"
        return f"{prefix} [{provider}:{model}:v1:{short_hash}]"
