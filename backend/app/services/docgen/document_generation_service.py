from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
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
from app.llm import (
    LLMAuthError,
    LLMMessage,
    LLMRateLimitError,
    LLMRequest,
    LLMUpstreamError,
    get_llm_client,
)
from app.services.docgen.prompt_builders import build_cover_letter_prompt, build_resume_prompt
from app.services.matching.matching_service import MatchingService

logger = logging.getLogger(__name__)


class DocgenError(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class DocgenNotFoundError(DocgenError):
    pass


class DocgenPrerequisiteError(DocgenError):
    pass


class DocgenProviderUnavailableError(DocgenError):
    pass


class DocgenMisconfigurationError(DocgenError):
    pass


class DocgenInvalidResultError(DocgenError):
    pass


class DocumentGenerationService:
    def __init__(self, db: Session):
        self.db = db

    def generate_resume_draft(self, profile_id: int, vacancy_id: int | None) -> ResumeVersion:
        profile_facts = self._collect_profile_facts(profile_id)
        vacancy_facts = self._collect_vacancy_facts(vacancy_id) if vacancy_id is not None else {}
        tailoring = self._collect_tailoring(profile_id=profile_id, vacancy_id=vacancy_id)

        self._validate_prerequisites(document_type="resume", profile_facts=profile_facts)

        messages = build_resume_prompt(profile_facts, vacancy_facts, tailoring)
        response = self._generate_llm_response(messages)
        content_text = self._validate_generated_text(response.text, document_type="resume")

        metadata = self._build_generation_metadata(
            document_type="resume",
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            profile_facts=profile_facts,
            vacancy_facts=vacancy_facts,
            tailoring=tailoring,
            provider=response.provider,
            model=response.model,
            source="ai",
            status="draft",
        )

        draft = ResumeVersion(
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            content_text=content_text,
            source="ai",
            status="draft",
            title=self._build_title("AI resume draft", metadata),
            generation_metadata=metadata,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def generate_cover_letter_draft(self, profile_id: int, vacancy_id: int) -> CoverLetterVersion:
        profile_facts = self._collect_profile_facts(profile_id)
        vacancy_facts = self._collect_vacancy_facts(vacancy_id)
        tailoring = self._collect_tailoring(profile_id=profile_id, vacancy_id=vacancy_id)

        self._validate_prerequisites(document_type="cover_letter", profile_facts=profile_facts)

        messages = build_cover_letter_prompt(profile_facts, vacancy_facts, tailoring)
        response = self._generate_llm_response(messages)
        content_text = self._validate_generated_text(response.text, document_type="cover_letter")

        metadata = self._build_generation_metadata(
            document_type="cover_letter",
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            profile_facts=profile_facts,
            vacancy_facts=vacancy_facts,
            tailoring=tailoring,
            provider=response.provider,
            model=response.model,
            source="ai",
            status="draft",
        )

        draft = CoverLetterVersion(
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            content_text=content_text,
            source="ai",
            status="draft",
            title=self._build_title("AI cover letter draft", metadata),
            subject="Сопроводительное письмо",
            generation_metadata=metadata,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def _generate_llm_response(self, messages: list[LLMMessage]):
        try:
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
        except (LLMRateLimitError, LLMUpstreamError) as exc:
            logger.exception("docgen provider temporary failure")
            raise DocgenProviderUnavailableError(
                "Generation provider is temporarily unavailable. Please try again shortly."
            ) from exc
        except (NotImplementedError, ValueError, LLMAuthError) as exc:
            logger.exception("docgen provider misconfiguration")
            raise DocgenMisconfigurationError(
                "Generation provider is not configured correctly. Please contact support."
            ) from exc

    def _collect_profile_facts(self, profile_id: int) -> dict[str, Any]:
        profile = self.db.get(Profile, profile_id)
        if not profile:
            raise DocgenNotFoundError(f"Profile not found: {profile_id}")

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
            raise DocgenNotFoundError(f"Vacancy not found: {vacancy_id}")

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
                logger.exception(
                    "docgen tailoring fallback profile_id=%s vacancy_id=%s",
                    profile_id,
                    vacancy_id,
                )

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
        document_type: str,
        profile_id: int,
        vacancy_id: int | None,
        profile_facts: dict[str, Any],
        vacancy_facts: dict[str, Any],
        tailoring: dict[str, Any],
        provider: str,
        model: str | None,
        source: str,
        status: str,
    ) -> dict[str, Any]:
        payload = {
            "profile_facts": profile_facts,
            "vacancy_facts": vacancy_facts,
            "tailoring": tailoring,
        }
        input_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        return {
            "provider": provider,
            "model": model or "",
            "document_type": document_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile_id": profile_id,
            "vacancy_id": vacancy_id,
            "prompt_version": "v1",
            "input_hash": input_hash,
            "source": source,
            "status": status,
        }

    @staticmethod
    def _build_title(prefix: str, metadata: dict[str, Any]) -> str:
        short_hash = str(metadata.get("input_hash", ""))[:12]
        model = str(metadata.get("model") or "unknown-model")
        provider = str(metadata.get("provider") or "unknown-provider")
        return f"{prefix} [{provider}:{model}:v1:{short_hash}]"

    @staticmethod
    def _validate_prerequisites(*, document_type: str, profile_facts: dict[str, Any]) -> None:
        has_about = bool((profile_facts.get("summary_about") or "").strip())
        has_skills = bool(profile_facts.get("skills"))
        has_experience = bool(profile_facts.get("experiences"))

        if not (has_about or has_skills or has_experience):
            raise DocgenPrerequisiteError(
                f"Missing profile data required to generate {document_type.replace('_', ' ')}. "
                "Add summary, skills, or experience and try again."
            )

    @staticmethod
    def _validate_generated_text(text: str | None, *, document_type: str) -> str:
        normalized = (text or "").strip()
        min_chars = 120 if document_type == "resume" else 80

        if len(normalized) < min_chars or len(normalized.split()) < 15:
            raise DocgenInvalidResultError(
                f"Generated {document_type.replace('_', ' ')} content is invalid or too short. Please retry."
            )

        return normalized
