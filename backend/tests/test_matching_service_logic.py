import unittest
from types import SimpleNamespace

from app.services.matching.matching_service import MatchingService, build_scoring_config


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    def __init__(self, quality_score=None):
        self.quality_score = quality_score

    def execute(self, *_args, **_kwargs):
        return _FakeScalarResult(self.quality_score)


class MatchingServiceLogicTests(unittest.TestCase):
    def test_remote_vacancy_does_not_fail_city_mismatch(self):
        service = MatchingService(_FakeDB())
        service._get_vacancy_plain_text = lambda _vacancy_id: "Fully remote role"

        vacancy = SimpleNamespace(id=1, source="hh", title="Python Engineer", location="Berlin", description="remote")
        profile = SimpleNamespace(city="Moscow", location="Moscow", relocation_ok=False, remote_ok=True)

        result = service._evaluate_location_eligibility(vacancy=vacancy, profile=profile)
        self.assertEqual(result["reasons_failed"], [])
        self.assertIn("location_check_skipped_for_remote", result["debug_notes"])

    def test_location_mismatch_respects_relocation_flag(self):
        service = MatchingService(_FakeDB())
        service._get_vacancy_plain_text = lambda _vacancy_id: "Office only"
        service._is_relocation_required = lambda _vacancy: True

        vacancy = SimpleNamespace(id=2, source="hh", title="Backend Engineer", location="Warsaw", description="office")
        profile_fail = SimpleNamespace(city="Tbilisi", location="Tbilisi", relocation_ok=False, remote_ok=True)
        profile_warn = SimpleNamespace(city="Tbilisi", location="Tbilisi", relocation_ok=True, remote_ok=True)

        fail_result = service._evaluate_location_eligibility(vacancy=vacancy, profile=profile_fail)
        warn_result = service._evaluate_location_eligibility(vacancy=vacancy, profile=profile_warn)

        self.assertTrue(any("релокация" in reason.lower() for reason in fail_result["reasons_failed"]))
        self.assertEqual(warn_result["reasons_failed"], [])
        self.assertTrue(any("релокаци" in warning.lower() for warning in warn_result["warnings"]))

    def test_salary_fail_vs_warning(self):
        service = MatchingService(_FakeDB())
        profile = SimpleNamespace(salary_min=200000)

        hard_mismatch = SimpleNamespace(salary_to=150000, salary_from=120000)
        borderline = SimpleNamespace(salary_to=180000, salary_from=170000)

        hard_result = service._evaluate_salary_expectations(vacancy=hard_mismatch, profile=profile)
        borderline_result = service._evaluate_salary_expectations(vacancy=borderline, profile=profile)

        self.assertTrue(hard_result["reasons_failed"])
        self.assertFalse(borderline_result["reasons_failed"])
        self.assertTrue(borderline_result["warnings"])

    def test_low_quality_caps_strong_score(self):
        service = MatchingService(_FakeDB())

        quality_result = service._apply_quality_guard(
            raw_score=0.92,
            semantic_score=0.95,
            hard_coverage=0.70,
            skill_requirements_count=1,
            hard_requirements_count=1,
            quality_score=0.28,
        )

        self.assertLessEqual(quality_result["score"], 0.64)
        self.assertIn("very_low_parsing_quality_cap", quality_result["penalties"])
        self.assertIn("sparse_skill_requirements_cap", quality_result["penalties"])

    def test_experience_constraint_extraction_and_fail(self):
        service = MatchingService(_FakeDB())
        service._get_vacancy_plain_text = lambda _vacancy_id: "Требования: не менее 5 лет коммерческого опыта"

        vacancy = SimpleNamespace(id=5, source="hh", title="Python Engineer", description=None)
        profile = SimpleNamespace(years_total=3.5)

        result = service._evaluate_experience_constraints(vacancy=vacancy, profile=profile)
        self.assertTrue(result["reasons_failed"])
        self.assertIn("5", result["reasons_failed"][0])

    def test_missing_hard_skills_are_explicit_in_diagnostic(self):
        note = MatchingService._build_semantic_vs_ats_note(
            semantic_score=0.88,
            hard_coverage=0.4,
            hard_missing=["Kubernetes", "Kafka"],
        )
        self.assertIn("ATS", note)

        note_with_missing = MatchingService._build_semantic_vs_ats_note(
            semantic_score=0.6,
            hard_coverage=0.6,
            hard_missing=["Kubernetes"],
        )
        self.assertIn("Kubernetes", note_with_missing)

    def test_build_scoring_config_applies_partial_override(self):
        config = build_scoring_config(
            {
                "weights": {"semantic": 0.55},
                "verdict_thresholds": {"strong_min": 0.8},
            }
        )
        self.assertEqual(config.weights.semantic, 0.55)
        self.assertEqual(config.weights.hard_coverage, 0.35)
        self.assertEqual(config.verdicts.strong_min, 0.8)
        self.assertEqual(config.verdicts.ok_min, 0.5)


if __name__ == "__main__":
    unittest.main()
