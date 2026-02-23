"""Service for ATS + semantic matching between profile and vacancy.

Example:
    from app.db.session import SessionLocal
    from app.services.matching.matching_service import MatchingService

    db = SessionLocal()
    try:
        service = MatchingService(db)
        score = service.compute_for_pair(profile_id=1, vacancy_id=42)
        tailoring = service.get_tailoring(profile_id=1, vacancy_id=42)
    finally:
        db.close()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import (
    Profile,
    ProfileEmbedding,
    ResumeEvidence,
    Vacancy,
    VacancyEmbedding,
    VacancyRequirement,
    VacancyScore,
)
from app.services.matching.utils import (
    extract_profile_tokens,
    find_evidence_snippet,
    normalize_skill,
)


logger = logging.getLogger(__name__)

MIN_RESUME_TEXT_LEN = 280


class MatchingService:
    """Computes layered matching score for profile-vacancy pair."""

    def __init__(self, db: Session):
        self.db = db

    def compute_for_pair(self, profile_id: int, vacancy_id: int) -> VacancyScore:
        """Compute layer1/layer2/final score, persist VacancyScore and ResumeEvidence."""
        profile = self.db.get(Profile, profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        vacancy = self.db.get(Vacancy, vacancy_id)
        if not vacancy:
            raise ValueError(f"Vacancy not found: {vacancy_id}")

        requirements = self.db.execute(
            select(VacancyRequirement).where(
                VacancyRequirement.vacancy_id == vacancy_id,
                VacancyRequirement.kind == "skill",
            )
        ).scalars().all()

        resume_text = profile.resume_text or ""
        skills_text = profile.skills_text or ""
        profile_text = "\n".join(part for part in [resume_text, skills_text] if part)

        layer1_score, ats, matched_evidence = self._compute_layer1(
            requirements,
            profile_text,
            resume_text=resume_text,
            skills_text=skills_text,
        )

        layer2_score = self._compute_layer2(profile_id=profile_id, vacancy_id=vacancy_id)

        hard_missing = ats["keywords_missing_must"]
        eligibility_ok = len(hard_missing) == 0
        reasons_failed = ["missing_required_skills"] if not eligibility_ok else []

        final_score = 0.55 * layer2_score + 0.45 * layer1_score

        if not eligibility_ok:
            verdict = "reject"
        elif final_score >= 0.70:
            verdict = "strong"
        elif final_score >= 0.40:
            verdict = "ok"
        else:
            verdict = "weak"

        explanation = {
            "eligibility": {
                "ok": eligibility_ok,
                "reasons_failed": reasons_failed,
            },
            "ats": ats,
            "semantic": {"score": layer2_score},
            "final": {"score": final_score, "verdict": verdict},
            "cover_letter_points": self._build_cover_letter_points(matched_evidence),
        }

        self._refresh_evidence(
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            matched_evidence=matched_evidence,
        )

        stmt = insert(VacancyScore).values(
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            layer1_score=layer1_score,
            layer2_score=layer2_score,
            final_score=final_score,
            verdict=verdict,
            explanation=explanation,
            computed_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_vacancy_scores_profile_vacancy",
            set_={
                "layer1_score": stmt.excluded.layer1_score,
                "layer2_score": stmt.excluded.layer2_score,
                "final_score": stmt.excluded.final_score,
                "verdict": stmt.excluded.verdict,
                "explanation": stmt.excluded.explanation,
                "computed_at": stmt.excluded.computed_at,
            },
        )

        self.db.execute(stmt)
        self.db.commit()

        return self.db.execute(
            select(VacancyScore).where(
                VacancyScore.profile_id == profile_id,
                VacancyScore.vacancy_id == vacancy_id,
            )
        ).scalar_one()

    def compute_recommendations(self, profile_id: int, limit: int = 50) -> list[VacancyScore]:
        """Compute recommendations for profile from top-N semantic nearest vacancies."""
        if self.db.get(ProfileEmbedding, profile_id) is None:
            raise ValueError(f"Profile embedding not found for profile_id={profile_id}")

        top_vacancy_rows = self.db.execute(
            text(
                """
                SELECT v.id AS vacancy_id,
                       ve.vacancy_id IS NOT NULL AS has_embedding,
                       (1 - (ve.embedding <=> pe.embedding)) AS semantic
                FROM vacancies v
                JOIN profile_embeddings pe ON pe.profile_id = :profile_id
                LEFT JOIN vacancy_embeddings ve ON ve.vacancy_id = v.id
                ORDER BY (ve.vacancy_id IS NULL), ve.embedding <=> pe.embedding
                """
            ),
            {"profile_id": profile_id},
        ).all()

        scores: list[VacancyScore] = []
        for row in top_vacancy_rows:
            if not row.has_embedding:
                logger.warning(
                    "Skipping vacancy without embedding in recommendations | profile_id=%s vacancy_id=%s",
                    profile_id,
                    row.vacancy_id,
                )
                continue

            scores.append(self.compute_for_pair(profile_id=profile_id, vacancy_id=row.vacancy_id))
            if len(scores) >= limit:
                break

        return sorted(scores, key=lambda score: score.final_score, reverse=True)

    def get_tailoring(self, profile_id: int, vacancy_id: int) -> dict[str, Any]:
        """Return explanation and evidence list to display tailoring recommendations."""
        score = self.db.execute(
            select(VacancyScore).where(
                VacancyScore.profile_id == profile_id,
                VacancyScore.vacancy_id == vacancy_id,
            )
        ).scalar_one_or_none()

        evidence_rows = self.db.execute(
            select(ResumeEvidence.evidence_text, ResumeEvidence.confidence)
            .where(
                ResumeEvidence.profile_id == profile_id,
                ResumeEvidence.vacancy_id == vacancy_id,
            )
            .order_by(ResumeEvidence.confidence.desc(), ResumeEvidence.id.asc())
        ).all()

        return {
            "explanation": score.explanation if score else {},
            "evidence": [{"text": row.evidence_text, "confidence": row.confidence} for row in evidence_rows],
        }

    def _compute_layer1(
        self,
        requirements: list[VacancyRequirement],
        profile_text: str,
        resume_text: str,
        skills_text: str,
    ) -> tuple[float, dict[str, list[str]], list[tuple[VacancyRequirement, str, float]]]:
        total_weight = sum(max(req.weight, 0) for req in requirements)
        matched_weight = 0
        profile_tokens = extract_profile_tokens(profile_text)

        keywords_present: list[str] = []
        keywords_missing_must: list[str] = []
        keywords_missing_nice: list[str] = []
        keywords_uncertain: list[str] = []
        matched_evidence: list[tuple[VacancyRequirement, str, float]] = []

        for req in requirements:
            needle = req.normalized_key or req.raw_text
            evidence = find_evidence_snippet(profile_text, needle)
            matched = evidence is not None

            if matched:
                matched_weight += max(req.weight, 0)
                keywords_present.append(req.raw_text)
                evidence_text, confidence = evidence
                matched_evidence.append((req, evidence_text, confidence))
            elif req.is_hard:
                keywords_missing_must.append(req.raw_text)
                if self._has_uncertain_token_match(req, profile_tokens):
                    keywords_uncertain.append(req.raw_text)
            else:
                keywords_missing_nice.append(req.raw_text)
                if self._has_uncertain_token_match(req, profile_tokens):
                    keywords_uncertain.append(req.raw_text)

        layer1_score = (matched_weight / total_weight) if total_weight > 0 else 0.0

        ats = {
            "keywords_present": self._unique(keywords_present),
            "keywords_missing_must": self._unique(keywords_missing_must),
            "keywords_missing_nice": self._unique(keywords_missing_nice),
            "keywords_uncertain": self._unique(keywords_uncertain),
            "keywords_to_add": self._unique(keywords_missing_nice + keywords_uncertain),
        }

        ats["structure_suggestions"] = self._build_structure_suggestions(
            keywords_missing_must=ats["keywords_missing_must"],
            resume_text=resume_text,
            skills_text=skills_text,
        )

        return layer1_score, ats, matched_evidence

    def _compute_layer2(self, profile_id: int, vacancy_id: int) -> float:
        # Явно читаем записи embedding.
        profile_embedding_exists = self.db.get(ProfileEmbedding, profile_id) is not None
        vacancy_embedding_exists = self.db.get(VacancyEmbedding, vacancy_id) is not None
        if not profile_embedding_exists or not vacancy_embedding_exists:
            return 0.0

        score = self.db.execute(
            text(
                """
                SELECT 1 - (ve.embedding <=> pe.embedding) AS similarity
                FROM vacancy_embeddings ve
                JOIN profile_embeddings pe ON pe.profile_id = :profile_id
                WHERE ve.vacancy_id = :vacancy_id
                """
            ),
            {"profile_id": profile_id, "vacancy_id": vacancy_id},
        ).scalar_one_or_none()

        if score is None:
            return 0.0

        return float(max(0.0, min(1.0, score)))

    def _refresh_evidence(
        self,
        profile_id: int,
        vacancy_id: int,
        matched_evidence: list[tuple[VacancyRequirement, str, float]],
    ) -> None:
        self.db.execute(
            delete(ResumeEvidence).where(
                ResumeEvidence.profile_id == profile_id,
                ResumeEvidence.vacancy_id == vacancy_id,
            )
        )

        for req, evidence_text, confidence in matched_evidence:
            self.db.add(
                ResumeEvidence(
                    profile_id=profile_id,
                    vacancy_id=vacancy_id,
                    requirement_id=req.id,
                    evidence_text=evidence_text,
                    evidence_type="skill_match",
                    confidence=float(confidence),
                )
            )

    @staticmethod
    def _build_cover_letter_points(matched_evidence: list[tuple[VacancyRequirement, str, float]]) -> list[str]:
        points: list[str] = []
        for req, evidence_text, _ in matched_evidence[:3]:
            skill = req.raw_text
            normalized = normalize_skill(skill)
            if normalized:
                points.append(f"Подкрепите навык '{skill}' фактом из резюме: {evidence_text}")

        return points

    @staticmethod
    def _build_structure_suggestions(
        keywords_missing_must: list[str], resume_text: str, skills_text: str
    ) -> list[str]:
        suggestions = [
            "Опишите достижения в формате 'действие → результат → метрика'.",
        ]
        if not skills_text or not skills_text.strip():
            suggestions.append("Добавьте раздел Skills с ключевыми навыками.")
        if len((resume_text or "").strip()) < MIN_RESUME_TEXT_LEN:
            suggestions.append("Расширьте описание опыта: добавьте задачи, результаты и метрики.")
        if keywords_missing_must:
            suggestions.append("Явно укажите обязательные навыки в опыте и summary.")
        return suggestions

    @staticmethod
    def _has_uncertain_token_match(requirement: VacancyRequirement, profile_tokens: set[str]) -> bool:
        normalized_req = normalize_skill(requirement.normalized_key or requirement.raw_text)
        if not normalized_req:
            return False

        req_tokens = [token for token in normalized_req.split() if len(token) >= 3]
        return any(token in profile_tokens for token in req_tokens)

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
