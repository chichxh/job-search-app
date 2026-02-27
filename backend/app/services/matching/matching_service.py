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
import re
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
    VacancyParsed,
    VacancyRequirement,
    VacancyScore,
)
from app.services.matching.utils import (
    contains_token,
    extract_profile_tokens,
    find_evidence_snippet,
    has_uncertain_match,
    normalize_skill,
    tokenize,
)
from app.services.vacancy_parsing.requirement_markers import EXCEPTIONS
from app.utils.text_clean import strip_html


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

        coverage, ats, matched_evidence = self._compute_layer1(
            requirements,
            profile_text,
            resume_text=resume_text,
            skills_text=skills_text,
        )
        hard_coverage = coverage["hard"]
        nice_coverage = coverage["nice"]
        skill_requirements_count = len(requirements)

        semantic_score = self._compute_layer2(profile_id=profile_id, vacancy_id=vacancy_id)

        hard_missing = ats["keywords_missing_must"]
        reasons_failed: list[str] = []
        warnings: list[str] = []
        explanation_warnings: list[str] = []

        if skill_requirements_count == 0:
            explanation_warnings.append("no_skill_requirements_extracted")

        if hard_missing:
            reasons_failed.append("missing_required_skills")

        relocation_required = self._is_relocation_required(vacancy)
        if relocation_required and not profile.relocation_ok:
            reasons_failed.append("Требуется релокация")

        if self._is_location_mismatch(vacancy=vacancy, profile=profile):
            reasons_failed.append("Несовпадение локации")

        if profile.salary_min is not None:
            if vacancy.salary_to is not None and vacancy.salary_to < profile.salary_min:
                reasons_failed.append("Ожидания по зарплате выше вилки")
            elif vacancy.salary_from is not None and vacancy.salary_from < profile.salary_min:
                warnings.append("Нижняя граница зарплаты ниже ожиданий")

        vacancy_level = self._detect_vacancy_level(vacancy.title or "")
        profile_level = self._detect_profile_level(profile.resume_text or "")
        overqualified = vacancy_level == "junior" and profile_level == "senior"
        if overqualified:
            warnings.append("overqualified")

        eligibility_ok = len(reasons_failed) == 0

        penalties: list[str] = []
        raw_score = 0.45 * semantic_score + 0.35 * hard_coverage + 0.20 * nice_coverage

        if overqualified:
            raw_score *= 0.9
            penalties.append("overqualified")

        has_salary_warning = any("зарплаты" in warning for warning in warnings)
        if has_salary_warning:
            raw_score *= 0.95
            penalties.append("salary_warning")

        if skill_requirements_count == 0:
            raw_score = min(raw_score, 0.65)
            penalties.append("no_skill_requirements_cap")

        raw_score = float(max(0.0, min(1.0, raw_score)))
        final_score = 0.0 if not eligibility_ok else raw_score

        if not eligibility_ok:
            verdict = "reject"
        elif raw_score >= 0.75:
            verdict = "strong"
        elif raw_score >= 0.50:
            verdict = "ok"
        elif raw_score >= 0.30:
            verdict = "weak"
        else:
            verdict = "reject"

        explanation = {
            "warnings": self._unique(explanation_warnings),
            "eligibility": {
                "ok": eligibility_ok,
                "reasons_failed": self._unique(reasons_failed),
                "warnings": self._unique(warnings),
            },
            "ats": ats,
            "semantic": {"score": semantic_score},
            "final": {
                "score": final_score,
                "raw_score": raw_score,
                "verdict": verdict,
                "components": {
                    "semantic": semantic_score,
                    "hard": hard_coverage,
                    "nice": nice_coverage,
                },
                "penalties": penalties,
            },
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
            layer1_score=(hard_coverage + nice_coverage) / 2,
            layer2_score=semantic_score,
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
                JOIN profile_embeddings_v2 pe ON pe.profile_id = :profile_id
                LEFT JOIN vacancy_embeddings_v2 ve ON ve.vacancy_id = v.id
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
    ) -> tuple[dict[str, float], dict[str, list[str]], list[tuple[VacancyRequirement, str, float]]]:
        matched_hard_weight = 0
        total_hard_weight = 0
        matched_nice_weight = 0
        total_nice_weight = 0
        profile_tokens = extract_profile_tokens(profile_text)

        keywords_present: list[str] = []
        keywords_missing_must: list[str] = []
        keywords_missing_nice: list[str] = []
        keywords_uncertain: list[str] = []
        matched_evidence: list[tuple[VacancyRequirement, str, float]] = []

        for req in requirements:
            needle = req.normalized_key or req.raw_text
            normalized_needle = normalize_skill(needle)
            term_tokens = tokenize(normalized_needle)
            exact_keyword_match = contains_token(profile_tokens, term_tokens)

            req_weight = max(req.weight, 0)
            if req.is_hard:
                total_hard_weight += req_weight
            else:
                total_nice_weight += req_weight

            if exact_keyword_match:
                if req.is_hard:
                    matched_hard_weight += req_weight
                else:
                    matched_nice_weight += req_weight
                keywords_present.append(req.raw_text)
                evidence = find_evidence_snippet(profile_text, needle)
                if evidence:
                    evidence_text, confidence = evidence
                    matched_evidence.append((req, evidence_text, confidence))
            elif req.is_hard:
                keywords_missing_must.append(req.raw_text)
                if has_uncertain_match(profile_tokens, normalized_needle):
                    keywords_uncertain.append(req.raw_text)
            else:
                keywords_missing_nice.append(req.raw_text)
                if has_uncertain_match(profile_tokens, normalized_needle):
                    keywords_uncertain.append(req.raw_text)

        hard_coverage = (matched_hard_weight / total_hard_weight) if total_hard_weight > 0 else 0.0
        nice_coverage = (matched_nice_weight / total_nice_weight) if total_nice_weight > 0 else 0.0

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

        return {"hard": hard_coverage, "nice": nice_coverage}, ats, matched_evidence

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
                FROM vacancy_embeddings_v2 ve
                JOIN profile_embeddings_v2 pe ON pe.profile_id = :profile_id
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


    def _get_vacancy_plain_text(self, vacancy_id: int) -> str | None:
        return self.db.execute(
            select(VacancyParsed.plain_text).where(VacancyParsed.vacancy_id == vacancy_id)
        ).scalar_one_or_none()

    def _is_relocation_required(self, vacancy: Vacancy) -> bool:
        if vacancy.source != "hh":
            return False

        vacancy_plain_text = self._get_vacancy_plain_text(vacancy.id)
        description = (vacancy_plain_text or strip_html(vacancy.description or "")).lower()

        not_relocation_patterns = EXCEPTIONS.get("not_relocation_patterns", [])
        if any(re.search(pattern, description) for pattern in not_relocation_patterns):
            return False

        relocation_markers = (
            "релокац",
            "переезд в",
            "готовность к переезду",
            "обязателен переезд",
            "relocation",
        )

        # Self-check examples:
        # "переезд на Go" -> relocation_required=False
        # "релокация в Республику Татарстан" -> relocation_required=True
        return any(marker in description for marker in relocation_markers)

    def _is_remote_vacancy(self, vacancy: Vacancy) -> bool:
        vacancy_plain_text = self._get_vacancy_plain_text(vacancy.id)
        haystack = " ".join(
            part.lower()
            for part in [vacancy.title or "", vacancy.location or "", vacancy_plain_text or strip_html(vacancy.description or "")]
            if part
        )
        remote_tokens = ("удален", "remote", "дистанцион")
        return any(token in haystack for token in remote_tokens)

    def _is_location_mismatch(self, vacancy: Vacancy, profile: Profile) -> bool:
        if not vacancy.location or not profile.location:
            return False
        if self._is_remote_vacancy(vacancy):
            return False
        return vacancy.location.strip() != profile.location.strip()

    @staticmethod
    def _detect_vacancy_level(title: str) -> str | None:
        lowered = (title or "").lower()
        if "junior" in lowered or "джуниор" in lowered:
            return "junior"
        if "senior" in lowered or "сеньор" in lowered:
            return "senior"
        if "middle" in lowered or "мидл" in lowered:
            return "middle"
        return None

    @staticmethod
    def _detect_profile_level(resume_text: str) -> str | None:
        lowered = (resume_text or "").lower()
        if "6+" in lowered or "senior" in lowered or "сеньор" in lowered:
            return "senior"
        if "middle" in lowered or "мидл" in lowered:
            return "middle"
        if "junior" in lowered or "джуниор" in lowered:
            return "junior"
        return None

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
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
