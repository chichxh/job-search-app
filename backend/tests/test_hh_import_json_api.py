from __future__ import annotations

import json
from pathlib import Path

from app.db import models

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "hh"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_import_hh_json_happy_path(client, auth_headers, fake_db) -> None:
    fixture = _load_fixture("hh_import_envelope_happy.json")

    response = client.post(
        "/api/v1/integrations/hh/import-json",
        headers=auth_headers,
        json={"consent": True, "payload": fixture},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resume_id"] == "res-basic"
    assert body["replaced_sections"] == ["experiences", "skills", "languages", "links"]

    profile = fake_db.get(models.Profile, 1)
    assert profile.title == "Python Backend Engineer"
    assert profile.salary_min == 220000
    assert profile.resume_text == "Backend engineer with FastAPI"


def test_import_hh_json_with_resume_id_selection(client, auth_headers, fake_db) -> None:
    fixture = _load_fixture("hh_import_envelope_happy.json")

    response = client.post(
        "/api/v1/integrations/hh/import-json",
        headers=auth_headers,
        json={"consent": True, "payload": fixture, "resume_id": "res-full"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resume_id"] == "res-full"

    profile = fake_db.get(models.Profile, 1)
    assert profile.full_name == "Petrov Ivan"
    assert profile.salary_min == 350000
    assert "Kubernetes" in (profile.skills_text or "")


def test_import_hh_json_salary_normalization_from_to(client, auth_headers, fake_db) -> None:
    fixture = _load_fixture("hh_import_edge_shapes.json")

    response = client.post(
        "/api/v1/integrations/hh/import-json",
        headers=auth_headers,
        json={"consent": True, "payload": fixture},
    )

    assert response.status_code == 200

    profile = fake_db.get(models.Profile, 1)
    assert profile.salary_min == 180000


def test_import_hh_json_experience_date_normalization_from_string(client, auth_headers, fake_db) -> None:
    fixture = _load_fixture("hh_import_edge_shapes.json")

    response = client.post(
        "/api/v1/integrations/hh/import-json",
        headers=auth_headers,
        json={"consent": True, "payload": fixture},
    )

    assert response.status_code == 200

    experiences = fake_db.query(models.ProfileExperience).all()
    assert len(experiences) == 1
    assert experiences[0].start_date.isoformat() == "2020-02-15"
    assert experiences[0].end_date.isoformat() == "2021-11-01"


def test_import_hh_json_invalid_payload_shape_returns_400(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/integrations/hh/import-json",
        headers=auth_headers,
        json={"consent": True, "payload": {"foo": "bar"}},
    )

    assert response.status_code == 400
    assert "payload" in response.json()["detail"].lower() or "format" in response.json()["detail"].lower()


def test_import_hh_json_requires_explicit_consent(client, auth_headers) -> None:
    fixture = _load_fixture("hh_import_edge_shapes.json")

    response = client.post(
        "/api/v1/integrations/hh/import-json",
        headers=auth_headers,
        json={"consent": False, "payload": fixture},
    )

    assert response.status_code == 400
    assert "consent" in response.json()["detail"].lower()
