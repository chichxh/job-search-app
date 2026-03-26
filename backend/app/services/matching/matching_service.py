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
    ProfileExperience,
    ProfileProject,
    ProfileSkill,
    ResumeEvidence,
    ResumeVersion,
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
SALARY_HARD_MISMATCH_RATIO = 0.85
SALARY_FROM_SEVERE_RATIO = 0.70
QUALITY_SCORE_LOW_THRESHOLD = 0.45
QUALITY_SCORE_VERY_LOW_THRESHOLD = 0.30
QUALITY_CAP_LOW = 0.74
QUALITY_CAP_VERY_LOW = 0.64
QUALITY_CAP_SPARSE_REQUIREMENTS = 0.72
MIN_RELIABLE_SKILL_REQUIREMENTS = 2
EXPERIENCE_FAIL_TOLERANCE_YEARS = 0.75
EXPERIENCE_WARNING_TOLERANCE_YEARS = 0.0

REMOTE_MARKERS = ("удален", "remote", "дистанцион", "work from home", "wfh")
OFFICE_REQUIRED_PATTERNS = (
    r"\boffice\s*only\b",
    r"\bonly\s+office\b",
    r"только\s+в\s+офис",
    r"работа\s+в\s+офисе",
    r"без\s+удал[её]н",
)
HYBRID_MARKERS = ("гибрид", "hybrid")
MIN_EXPERIENCE_PATTERNS = (
    re.compile(r"\b(\d+(?:[.,]\d+)?)\s*\+\s*(?:years?|yrs?|лет|года?)\b", re.IGNORECASE),
    re.compile(r"\b(?:from|at\s+least|minimum|min)\s+(\d+(?:[.,]\d+)?)\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"\b(?:от|не\s+менее|минимум)\s*(\d+(?:[.,]\d+)?)\s*(?:лет|года?)\b", re.IGNORECASE),
)


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

        resume_text = self._get_active_resume_text(profile_id=profile_id) or (profile.resume_text or "")
        experiences_text = self._get_experiences_text(profile_id=profile_id)
        projects_text = self._get_projects_text(profile_id=profile_id)
        profile_text = "\n".join(
            part
            for part in [
                resume_text,
                profile.summary_about or "",
                experiences_text,
                projects_text,
            ]
            if part
        )
        profile_skill_levels = self._get_profile_skill_levels(profile_id=profile_id)
        profile_skills_set = set(profile_skill_levels)

        coverage, ats, matched_evidence = self._compute_layer1(
            requirements,
            profile_text,
            resume_text=resume_text,
            skills_text=profile.skills_text or "",
            profile_skills_set=profile_skills_set,
            profile_skill_levels=profile_skill_levels,
            experience_projects_text="\n".join(part for part in [experiences_text, projects_text] if part),
        )
        hard_coverage = coverage["hard"]
        nice_coverage = coverage["nice"]
        skill_requirements_count = len(requirements)

        semantic_score = self._compute_layer2(profile_id=profile_id, vacancy_id=vacancy_id)

        hard_missing = ats["keywords_missing_must"]
        hard_requirements_count = len(hard_missing) + len(ats["keywords_present"])
        reasons_failed: list[str] = []
        warnings: list[str] = []
        explanation_warnings: list[str] = []

        if skill_requirements_count == 0:
            explanation_warnings.append("no_skill_requirements_extracted")

        if hard_missing:
            reasons_failed.append("missing_required_skills")

        location_eval = self._evaluate_location_eligibility(vacancy=vacancy, profile=profile)
        reasons_failed.extend(location_eval["reasons_failed"])
        warnings.extend(location_eval["warnings"])

        explanation_warnings.extend(
            [
                f"preferred_schedule={profile.preferred_schedule}" if profile.preferred_schedule else "",
                f"preferred_employment={profile.preferred_employment}" if profile.preferred_employment else "",
                f"relocation_ok={profile.relocation_ok}",
                f"remote_ok={profile.remote_ok}",
                f"available_from={profile.available_from.isoformat()}" if profile.available_from else "",
                f"notice_period_days={profile.notice_period_days}"
                if profile.notice_period_days is not None
                else "",
                f"vacancy_work_mode={location_eval['work_mode']}",
            ]
        )
        explanation_warnings.extend(location_eval["debug_notes"])

        salary_eval = self._evaluate_salary_expectations(vacancy=vacancy, profile=profile)
        reasons_failed.extend(salary_eval["reasons_failed"])
        warnings.extend(salary_eval["warnings"])

        experience_eval = self._evaluate_experience_constraints(vacancy=vacancy, profile=profile)
        reasons_failed.extend(experience_eval["reasons_failed"])
        warnings.extend(experience_eval["warnings"])
        explanation_warnings.extend(experience_eval["debug_notes"])

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

        vacancy_quality_score = self._get_vacancy_quality_score(vacancy_id=vacancy_id)
        quality_eval = self._apply_quality_guard(
            raw_score=raw_score,
            semantic_score=semantic_score,
            hard_coverage=hard_coverage,
            skill_requirements_count=skill_requirements_count,
            hard_requirements_count=hard_requirements_count,
            quality_score=vacancy_quality_score,
        )
        raw_score = quality_eval["score"]
        penalties.extend(quality_eval["penalties"])
        warnings.extend(quality_eval["warnings"])

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
            "quality_guard": quality_eval["diagnostics"],
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
                "semantic_vs_ats": self._build_semantic_vs_ats_note(
                    semantic_score=semantic_score,
                    hard_coverage=hard_coverage,
                    hard_missing=hard_missing,
                ),
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
        profile_skills_set: set[str],
        profile_skill_levels: dict[str, str],
        experience_projects_text: str,
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
            skill_present = normalized_needle in profile_skills_set if normalized_needle else False
            exact_keyword_match = contains_token(profile_tokens, term_tokens)
            beginner_hard_skill = (
                skill_present
                and req.is_hard
                and profile_skill_levels.get(normalized_needle) == "beginner"
            )
            is_present = (skill_present and not beginner_hard_skill) or exact_keyword_match

            req_weight = max(req.weight, 0)
            if req.is_hard:
                total_hard_weight += req_weight
            else:
                total_nice_weight += req_weight

            if is_present:
                if req.is_hard:
                    matched_hard_weight += req_weight
                else:
                    matched_nice_weight += req_weight
                keywords_present.append(req.raw_text)

                evidence = None
                if skill_present:
                    evidence = find_evidence_snippet(experience_projects_text, needle)
                    if not evidence:
                        evidence = find_evidence_snippet(resume_text, needle)
                if not evidence:
                    evidence = find_evidence_snippet(profile_text, needle)

                if evidence:
                    evidence_text, confidence = evidence
                    matched_evidence.append((req, evidence_text, confidence))
            elif req.is_hard:
                keywords_missing_must.append(req.raw_text)
                if beginner_hard_skill:
                    keywords_uncertain.append(req.raw_text)
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

    def _get_active_resume_text(self, profile_id: int) -> str | None:
        return self.db.execute(
            select(ResumeVersion.content_text)
            .where(
                ResumeVersion.profile_id == profile_id,
                ResumeVersion.status == "approved",
                ResumeVersion.vacancy_id.is_(None),
            )
            .order_by(
                ResumeVersion.approved_at.desc().nullslast(),
                ResumeVersion.created_at.desc(),
                ResumeVersion.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def _get_experiences_text(self, profile_id: int, limit: int = 5) -> str:
        experiences = self.db.execute(
            select(ProfileExperience)
            .where(ProfileExperience.profile_id == profile_id)
            .order_by(
                ProfileExperience.start_date.desc(),
                ProfileExperience.end_date.desc().nullslast(),
                ProfileExperience.id.desc(),
            )
            .limit(limit)
        ).scalars().all()
        parts: list[str] = []
        for exp in experiences:
            parts.extend(
                [
                    exp.responsibilities_text or "",
                    exp.achievements_text or "",
                    exp.tech_stack_text or "",
                ]
            )
        return "\n".join(part for part in parts if part)

    def _get_projects_text(self, profile_id: int, limit: int = 5) -> str:
        projects = self.db.execute(
            select(ProfileProject)
            .where(ProfileProject.profile_id == profile_id)
            .order_by(
                ProfileProject.start_date.desc().nullslast(),
                ProfileProject.created_at.desc(),
                ProfileProject.id.desc(),
            )
            .limit(limit)
        ).scalars().all()
        parts: list[str] = []
        for project in projects:
            parts.extend([project.description_text or "", project.tech_stack_text or ""])
        return "\n".join(part for part in parts if part)

    def _get_profile_skill_levels(self, profile_id: int) -> dict[str, str]:
        rows = self.db.execute(
            select(ProfileSkill.normalized_key, ProfileSkill.level).where(ProfileSkill.profile_id == profile_id)
        ).all()
        level_priority = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
        result: dict[str, str] = {}
        for normalized_key, level in rows:
            if not normalized_key:
                continue
            normalized = normalize_skill(normalized_key)
            if not normalized:
                continue
            current_level = (level or "").strip().lower()
            previous_level = result.get(normalized, "")
            if level_priority.get(current_level, 0) >= level_priority.get(previous_level, 0):
                result[normalized] = current_level
        return result

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
        return self._detect_work_mode(vacancy) == "remote"

    def _detect_work_mode(self, vacancy: Vacancy) -> str:
        vacancy_plain_text = self._get_vacancy_plain_text(vacancy.id)
        haystack = " ".join(
            part.lower()
            for part in [vacancy.title or "", vacancy.location or "", vacancy_plain_text or strip_html(vacancy.description or "")]
            if part
        )
        if any(re.search(pattern, haystack) for pattern in OFFICE_REQUIRED_PATTERNS):
            return "office"
        has_remote = any(token in haystack for token in REMOTE_MARKERS)
        has_hybrid = any(token in haystack for token in HYBRID_MARKERS)
        if has_hybrid:
            return "hybrid"
        if has_remote:
            return "remote"
        return "office"

    def _evaluate_location_eligibility(self, vacancy: Vacancy, profile: Profile) -> dict[str, Any]:
        reasons_failed: list[str] = []
        warnings: list[str] = []
        notes: list[str] = []

        work_mode = self._detect_work_mode(vacancy)
        profile_city = (profile.city or profile.location or "").strip()
        vacancy_city = (vacancy.location or "").strip()
        relocation_required = self._is_relocation_required(vacancy)

        if work_mode == "remote":
            notes.append("location_check_skipped_for_remote")
            if not profile.remote_ok:
                warnings.append("Профиль отмечен как не remote, но вакансия remote")
            return {
                "reasons_failed": reasons_failed,
                "warnings": warnings,
                "debug_notes": notes,
                "work_mode": work_mode,
            }

        if vacancy_city and profile_city and vacancy_city != profile_city:
            if relocation_required and not profile.relocation_ok:
                reasons_failed.append("Требуется релокация, профиль не готов к переезду")
            elif not profile.relocation_ok:
                reasons_failed.append("Несовпадение локации без готовности к релокации")
            else:
                warnings.append("Несовпадение локации, требуется релокация")

        return {"reasons_failed": reasons_failed, "warnings": warnings, "debug_notes": notes, "work_mode": work_mode}

    def _evaluate_salary_expectations(self, vacancy: Vacancy, profile: Profile) -> dict[str, list[str]]:
        reasons_failed: list[str] = []
        warnings: list[str] = []
        if profile.salary_min is None or profile.salary_min <= 0:
            return {"reasons_failed": reasons_failed, "warnings": warnings}

        if vacancy.salary_to is not None and vacancy.salary_to < profile.salary_min:
            ratio = vacancy.salary_to / profile.salary_min
            if ratio < SALARY_HARD_MISMATCH_RATIO:
                reasons_failed.append("Ожидания по зарплате сильно выше вилки")
            else:
                warnings.append("Верхняя граница зарплаты чуть ниже ожиданий")
            return {"reasons_failed": reasons_failed, "warnings": warnings}

        if vacancy.salary_from is not None and vacancy.salary_from < profile.salary_min:
            ratio_from = vacancy.salary_from / profile.salary_min
            if ratio_from < SALARY_FROM_SEVERE_RATIO:
                warnings.append("Нижняя граница зарплаты значительно ниже ожиданий")
            else:
                warnings.append("Нижняя граница зарплаты ниже ожиданий")

        return {"reasons_failed": reasons_failed, "warnings": warnings}

    def _get_vacancy_quality_score(self, vacancy_id: int) -> float | None:
        row = self.db.execute(
            select(VacancyParsed.quality_score).where(VacancyParsed.vacancy_id == vacancy_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        return float(max(0.0, min(1.0, row)))

    def _evaluate_experience_constraints(self, vacancy: Vacancy, profile: Profile) -> dict[str, list[str]]:
        reasons_failed: list[str] = []
        warnings: list[str] = []
        debug_notes: list[str] = []
        min_years = self._extract_min_experience_years(vacancy)
        if min_years is None:
            return {"reasons_failed": reasons_failed, "warnings": warnings, "debug_notes": debug_notes}

        debug_notes.append(f"detected_min_experience_years={min_years}")
        if profile.years_total is None:
            warnings.append("Не удалось проверить требование по опыту: years_total не указан")
            return {"reasons_failed": reasons_failed, "warnings": warnings, "debug_notes": debug_notes}

        gap = profile.years_total - min_years
        debug_notes.append(f"profile_years_total={profile.years_total}")
        if gap < -EXPERIENCE_FAIL_TOLERANCE_YEARS:
            reasons_failed.append(f"Недостаточно общего опыта: требуется от {min_years:g} лет")
        elif gap < EXPERIENCE_WARNING_TOLERANCE_YEARS:
            warnings.append(f"Опыт близок к нижней границе требования ({min_years:g}+ лет)")

        return {"reasons_failed": reasons_failed, "warnings": warnings, "debug_notes": debug_notes}

    def _extract_min_experience_years(self, vacancy: Vacancy) -> float | None:
        vacancy_plain_text = self._get_vacancy_plain_text(vacancy.id)
        text_blob = " ".join(
            part for part in [vacancy.title or "", vacancy_plain_text or strip_html(vacancy.description or "")] if part
        )
        lowered = text_blob.lower()
        found_values: list[float] = []
        for pattern in MIN_EXPERIENCE_PATTERNS:
            for match in pattern.findall(lowered):
                normalized = str(match).replace(",", ".")
                try:
                    value = float(normalized)
                except ValueError:
                    continue
                if 0 < value <= 50:
                    found_values.append(value)
        if not found_values:
            return None
        return max(found_values)

    def _apply_quality_guard(
        self,
        raw_score: float,
        semantic_score: float,
        hard_coverage: float,
        skill_requirements_count: int,
        hard_requirements_count: int,
        quality_score: float | None,
    ) -> dict[str, Any]:
        score = raw_score
        penalties: list[str] = []
        warnings: list[str] = []
        applied_caps: list[str] = []

        if quality_score is not None:
            if quality_score < QUALITY_SCORE_VERY_LOW_THRESHOLD:
                score = min(score, QUALITY_CAP_VERY_LOW)
                penalties.append("very_low_parsing_quality_cap")
                warnings.append("Низкое качество parsing: strong verdict ограничен")
                applied_caps.append(f"quality_score<{QUALITY_SCORE_VERY_LOW_THRESHOLD}")
            elif quality_score < QUALITY_SCORE_LOW_THRESHOLD:
                score = min(score, QUALITY_CAP_LOW)
                penalties.append("low_parsing_quality_cap")
                warnings.append("Пониженное качество parsing: итоговый verdict ограничен")
                applied_caps.append(f"quality_score<{QUALITY_SCORE_LOW_THRESHOLD}")

        if skill_requirements_count == 0:
            score = min(score, QUALITY_CAP_VERY_LOW)
            penalties.append("no_skill_requirements_cap")
            warnings.append("Нет извлеченных skill requirements: ATS-сигнал слабый")
            applied_caps.append("skill_requirements_count==0")
        elif skill_requirements_count < MIN_RELIABLE_SKILL_REQUIREMENTS:
            score = min(score, QUALITY_CAP_SPARSE_REQUIREMENTS)
            penalties.append("sparse_skill_requirements_cap")
            warnings.append("Мало извлеченных skill requirements: semantic сигнал ограничен")
            applied_caps.append(f"skill_requirements_count<{MIN_RELIABLE_SKILL_REQUIREMENTS}")

        return {
            "score": score,
            "penalties": penalties,
            "warnings": warnings,
            "diagnostics": {
                "quality_score": quality_score,
                "skill_requirements_count": skill_requirements_count,
                "hard_requirements_count": hard_requirements_count,
                "semantic_score": semantic_score,
                "hard_coverage": hard_coverage,
                "applied_caps": applied_caps,
            },
        }

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
    def _build_semantic_vs_ats_note(semantic_score: float, hard_coverage: float, hard_missing: list[str]) -> str:
        if semantic_score >= 0.8 and hard_coverage < 0.5:
            return "Высокая semantic близость при слабом ATS-покрытии hard skills."
        if hard_missing:
            return f"Не закрыты обязательные навыки: {', '.join(hard_missing[:3])}."
        return "Semantic и ATS сигналы согласованы."

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
