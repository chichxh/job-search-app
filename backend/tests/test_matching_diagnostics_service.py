import unittest

from app.services.matching.diagnostics_service import MatchingDiagnosticsService, merge_quality_diagnostics


class MatchingDiagnosticsServiceTests(unittest.TestCase):
    def test_build_recommendation_breakdown_contains_compact_quality_fields(self):
        explanation = {
            "eligibility": {"warnings": ["salary_warning", "location_warning"]},
            "quality_guard": {"applied_caps": ["quality_score<0.45"]},
            "final": {
                "components": {"semantic": 0.82, "hard": 0.5, "nice": 0.25},
                "penalties": ["low_parsing_quality_cap", "salary_warning"],
            },
        }

        payload = MatchingDiagnosticsService.build_recommendation_breakdown(
            vacancy_id=42,
            title="Senior Python Engineer",
            final_score=0.61,
            verdict="ok",
            explanation=explanation,
        )

        self.assertEqual(payload["vacancy_id"], 42)
        self.assertEqual(payload["semantic_component"], 0.82)
        self.assertEqual(payload["hard_coverage"], 0.5)
        self.assertEqual(payload["nice_coverage"], 0.25)
        self.assertIn("salary_warning", payload["key_warnings"])
        self.assertIn("low_parsing_quality_cap", payload["key_penalties"])
        self.assertEqual(payload["quality_caps"], ["quality_score<0.45"])

    def test_merge_quality_diagnostics_has_stable_top_verdict(self):
        merged = merge_quality_diagnostics(
            global_summary={"total_vacancies": 10},
            profile_summary={"verdict_distribution": {"ok": 3, "weak": 1}},
        )
        self.assertEqual(merged["top_verdict"], "ok")


if __name__ == "__main__":
    unittest.main()
