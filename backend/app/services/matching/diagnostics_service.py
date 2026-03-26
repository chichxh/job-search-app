from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import ResumeEvidence, Vacancy, VacancyParsed, VacancyRequirement, VacancyScore


class MatchingDiagnosticsService:
    """Small diagnostics layer for parsing + matching quality checks."""

    def __init__(self, db: Session):
        self.db = db

    def build_global_summary(self, *, low_quality_threshold: float = 0.45) -> dict[str, Any]:
        total_vacancies = int(self.db.execute(select(func.count()).select_from(Vacancy)).scalar_one())
        vacancies_with_parsed = int(self.db.execute(select(func.count()).select_from(VacancyParsed)).scalar_one())

        vacancies_with_requirements_lines = int(
            self.db.execute(
                select(func.count())
                .select_from(VacancyParsed)
                .where(
                    text(
                        "jsonb_array_length(coalesce(sections_json->'requirements'->'lines','[]'::jsonb)) > 0"
                    )
                )
            ).scalar_one()
        )

        vacancies_with_skill_requirements = int(
            self.db.execute(
                select(func.count(func.distinct(VacancyRequirement.vacancy_id))).where(VacancyRequirement.kind == "skill")
            ).scalar_one()
        )

        vacancies_with_hard_requirements = int(
            self.db.execute(
                select(func.count(func.distinct(VacancyRequirement.vacancy_id))).where(
                    VacancyRequirement.kind == "skill",
                    VacancyRequirement.is_hard.is_(True),
                )
            ).scalar_one()
        )

        low_quality_vacancies_count = int(
            self.db.execute(
                select(func.count())
                .select_from(VacancyParsed)
                .where(VacancyParsed.quality_score < low_quality_threshold)
            ).scalar_one()
        )

        return {
            "total_vacancies": total_vacancies,
            "vacancies_with_vacancy_parsed": vacancies_with_parsed,
            "vacancies_with_requirements_lines_gt_0": vacancies_with_requirements_lines,
            "vacancies_with_skill_requirements_gt_0": vacancies_with_skill_requirements,
            "vacancies_with_hard_requirements_gt_0": vacancies_with_hard_requirements,
            "low_quality_threshold": low_quality_threshold,
            "low_quality_vacancies_count": low_quality_vacancies_count,
        }

    def build_profile_summary(
        self,
        *,
        profile_id: int,
        top_n: int = 10,
    ) -> dict[str, Any]:
        recommendation_count = int(
            self.db.execute(
                select(func.count())
                .select_from(VacancyScore)
                .where(VacancyScore.profile_id == profile_id)
            ).scalar_one()
        )

        verdict_distribution_rows = self.db.execute(
            select(VacancyScore.verdict, func.count())
            .where(VacancyScore.profile_id == profile_id)
            .group_by(VacancyScore.verdict)
        ).all()
        verdict_distribution = {verdict: int(count) for verdict, count in verdict_distribution_rows}

        recommendations_with_evidence = int(
            self.db.execute(
                select(func.count(func.distinct(VacancyScore.vacancy_id)))
                .select_from(VacancyScore)
                .join(
                    ResumeEvidence,
                    (ResumeEvidence.profile_id == VacancyScore.profile_id)
                    & (ResumeEvidence.vacancy_id == VacancyScore.vacancy_id),
                )
                .where(VacancyScore.profile_id == profile_id)
            ).scalar_one()
        )

        top_rows = self.db.execute(
            select(VacancyScore, Vacancy)
            .join(Vacancy, Vacancy.id == VacancyScore.vacancy_id)
            .where(VacancyScore.profile_id == profile_id)
            .order_by(VacancyScore.final_score.desc(), VacancyScore.id.asc())
            .limit(top_n)
        ).all()

        top_recommendations = [
            self.build_recommendation_breakdown(
                vacancy_id=vacancy.id,
                title=vacancy.title or "",
                final_score=score.final_score,
                verdict=score.verdict,
                explanation=score.explanation or {},
            )
            for score, vacancy in top_rows
        ]

        return {
            "profile_id": profile_id,
            "recommendations_count": recommendation_count,
            "verdict_distribution": verdict_distribution,
            "recommendations_with_evidence_gt_0": recommendations_with_evidence,
            "top_recommendations": top_recommendations,
        }

    @staticmethod
    def build_recommendation_breakdown(
        *,
        vacancy_id: int,
        title: str,
        final_score: float,
        verdict: str,
        explanation: dict[str, Any],
    ) -> dict[str, Any]:
        components = (
            (explanation.get("final") or {}).get("components") if isinstance(explanation, dict) else {}
        ) or {}
        eligibility = ((explanation.get("eligibility") or {}) if isinstance(explanation, dict) else {}) or {}
        quality_guard = ((explanation.get("quality_guard") or {}) if isinstance(explanation, dict) else {}) or {}
        final_part = ((explanation.get("final") or {}) if isinstance(explanation, dict) else {}) or {}

        warnings = list((eligibility.get("warnings") or [])[:3])
        penalties = list((final_part.get("penalties") or [])[:3])
        quality_caps = list((quality_guard.get("applied_caps") or [])[:2])

        return {
            "vacancy_id": vacancy_id,
            "title": title,
            "final_score": float(final_score),
            "verdict": verdict,
            "semantic_component": float(components.get("semantic", 0.0)),
            "hard_coverage": float(components.get("hard", 0.0)),
            "nice_coverage": float(components.get("nice", 0.0)),
            "key_warnings": warnings,
            "key_penalties": penalties,
            "quality_caps": quality_caps,
        }


def merge_quality_diagnostics(global_summary: dict[str, Any], profile_summary: dict[str, Any]) -> dict[str, Any]:
    """Utility for CLI/dev scripts: deterministic payload shape for snapshots."""

    top_verdicts = Counter(profile_summary.get("verdict_distribution") or {})
    return {
        "global": global_summary,
        "profile": profile_summary,
        "top_verdict": top_verdicts.most_common(1)[0][0] if top_verdicts else None,
    }
