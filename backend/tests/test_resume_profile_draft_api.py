from datetime import date
from app.db import models


SIMPLE_RESUME_TEXT = """John Doe
Senior Python Backend Engineer
Location: Berlin, Remote
Email: john@example.com
GitHub: https://github.com/johndoe
LinkedIn: https://linkedin.com/in/johndoe
Telegram: @johndev
Desired salary: 250000 RUB

Summary
Backend engineer with 6+ years in FastAPI and PostgreSQL.
Building scalable APIs and async services.

Experience
Jan 2021 - Present
Acme Corp
Senior Backend Engineer
Designed microservices, optimized PostgreSQL, owned CI/CD.

Mar 2018 - Dec 2020
Beta LLC
Backend Developer
Built Python services and integrations.

Skills
Python, FastAPI, PostgreSQL, Docker, Kubernetes, Python

Languages
English - C1
Russian - Native
"""


def _parse_payload(client, auth_headers):
    response = client.post(
        "/api/v1/profiles/1/resume-import/parse",
        headers=auth_headers,
        json={"extracted_text": SIMPLE_RESUME_TEXT},
    )
    assert response.status_code == 200
    return response.json()


def test_parse_resume_text_into_structured_draft(client, auth_headers):
    payload = _parse_payload(client, auth_headers)

    assert payload["draft"]["full_name"] == "John Doe"
    assert "Backend Engineer" in payload["draft"]["title"]
    assert payload["draft"]["salary_min"] == 250000
    assert len(payload["draft"]["experiences"]) >= 1
    assert any(skill["normalized_key"] == "python" for skill in payload["draft"]["skills"])
    assert any(link["type"] == "github" for link in payload["draft"]["links"])
    assert payload["applyability"]["has_useful_content"] is True


def test_apply_resume_draft_updates_profile_main_fields(client, auth_headers, fake_db):
    parsed = _parse_payload(client, auth_headers)

    response = client.post(
        "/api/v1/profiles/1/resume-import/apply",
        headers=auth_headers,
        json={
            "draft": parsed["draft"],
            "update_main_fields": True,
            "replace_sections": ["experiences", "skills", "languages", "links"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "full_name" in body["updated_fields"]
    assert "skills" in body["replaced_sections"]

    profile = fake_db.get(models.Profile, 1)
    assert profile.full_name == "John Doe"
    assert profile.salary_min == 250000
    assert "FastAPI" in (profile.skills_text or "")


def test_apply_resume_draft_replaces_experiences_and_dedupes_skills(client, auth_headers, fake_db):
    existing_experience = models.ProfileExperience(
        profile_id=1,
        company_name="Old Company",
        position_title="Old Role",
        location="Remote",
        start_date=date(2010, 1, 1),
        end_date=date(2011, 1, 1),
        is_current=False,
        responsibilities_text="old",
        achievements_text="",
    )
    fake_db.add(existing_experience)

    parsed = _parse_payload(client, auth_headers)
    parsed["draft"]["skills"].append(
        {
            "name_raw": "Python",
            "normalized_key": "python",
            "category": "hard_skill",
            "level": "intermediate",
            "is_primary": False,
        }
    )

    response = client.post(
        "/api/v1/profiles/1/resume-import/apply",
        headers=auth_headers,
        json={
            "draft": parsed["draft"],
            "update_main_fields": False,
            "replace_sections": ["experiences", "skills"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert any("duplicate skill" in warning.lower() for warning in body["warnings"])

    experiences = [item for item in fake_db.query(models.ProfileExperience).all() if item.profile_id == 1]
    assert len(experiences) >= 1
    assert all(item.company_name != "Old Company" for item in experiences)

    skills = [item for item in fake_db.query(models.ProfileSkill).all() if item.profile_id == 1]
    normalized = [item.normalized_key for item in skills]
    assert normalized.count("python") == 1


def test_parse_low_signal_resume_returns_error(client, auth_headers):
    response = client.post(
        "/api/v1/profiles/1/resume-import/parse",
        headers=auth_headers,
        json={"extracted_text": ".... ...."},
    )

    assert response.status_code == 422
    assert "nothing useful" in response.json()["detail"].lower() or "too short" in response.json()["detail"].lower()


def test_resume_parse_blocks_foreign_profile(client, foreign_auth_headers):
    response = client.post(
        "/api/v1/profiles/1/resume-import/parse",
        headers=foreign_auth_headers,
        json={"extracted_text": SIMPLE_RESUME_TEXT},
    )
    assert response.status_code == 404


def test_apply_invalid_empty_draft_returns_422(client, auth_headers):
    response = client.post(
        "/api/v1/profiles/1/resume-import/apply",
        headers=auth_headers,
        json={
            "draft": {
                "full_name": None,
                "title": None,
                "location": None,
                "summary_about": None,
                "salary_min": None,
                "experiences": [],
                "skills": [],
                "languages": [],
                "links": [],
                "warnings": [],
                "quality_hints": {},
            },
            "update_main_fields": True,
            "replace_sections": ["experiences"],
        },
    )

    assert response.status_code == 422
    assert "no useful content" in response.json()["detail"].lower()
