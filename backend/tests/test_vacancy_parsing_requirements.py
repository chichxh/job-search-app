import unittest

from app.services.requirements_extractor import extract_requirements_from_sections
from app.services.vacancy_parsing.hh_parser import parse_hh_description
from app.services.vacancy_parsing.line_classifier import classify_line


class VacancyParsingRequirementsTests(unittest.TestCase):
    def test_header_content_same_line_is_parsed_into_sections(self):
        html = """
        <p>Требования: опыт с Python и Node.js</p>
        <p>Skills: React, TypeScript</p>
        <p>Expectations: C# и ASP.NET</p>
        <p>Что важно: Docker Compose</p>
        """

        parsed = parse_hh_description(html)
        requirements_lines = parsed["sections"]["requirements"]["lines"]

        self.assertIn("опыт с Python и Node.js", requirements_lines)
        self.assertIn("React, TypeScript", requirements_lines)
        self.assertIn("C# и ASP.NET", requirements_lines)
        self.assertIn("Docker Compose", requirements_lines)

    def test_requirements_lines_not_empty_for_hh_like_text(self):
        html = """
        <p><strong>Требования к кандидату:</strong></p>
        <ul>
            <li>Опыт с Python от 3 лет</li>
            <li>Знание SQL и PostgreSQL</li>
        </ul>
        <p><strong>Будет плюсом:</strong></p>
        <ul><li>GraphQL</li></ul>
        """

        parsed = parse_hh_description(html)

        self.assertGreater(len(parsed["sections"]["requirements"]["lines"]), 0)
        self.assertGreaterEqual(parsed["quality_score"], 0.0)

    def test_line_classification_must_and_nice(self):
        self.assertEqual(classify_line("Требуется опыт с Kubernetes", current_section=None), "must")
        self.assertEqual(classify_line("Будет плюсом опыт с RabbitMQ", current_section=None), "nice")

    def test_skill_normalization_for_tricky_tokens(self):
        sections_json = {
            "requirements": {
                "lines": [
                    "Опыт с C++, C#, Node.js и Docker-Compose",
                ]
            },
            "nice_to_have": {"lines": []},
            "other": {"lines": []},
            "responsibilities": {"lines": []},
        }

        reqs = extract_requirements_from_sections(sections_json)
        keys = {req["normalized_key"] for req in reqs}

        self.assertIn("c++", keys)
        self.assertIn("c#", keys)
        self.assertIn("node.js", keys)
        self.assertIn("docker compose", keys)

    def test_no_git_false_positive_from_github(self):
        sections_json = {
            "requirements": {
                "lines": [
                    "Опыт с GitHub Actions и GitLab CI",
                ]
            },
            "nice_to_have": {"lines": []},
            "other": {"lines": []},
            "responsibilities": {"lines": []},
        }

        reqs = extract_requirements_from_sections(sections_json)
        raw_names = {req["raw_text"] for req in reqs}

        self.assertIn("GitHub Actions", raw_names)
        self.assertIn("GitLab CI", raw_names)
        self.assertNotIn("Git", raw_names)


if __name__ == "__main__":
    unittest.main()
