from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.routers.docgen import DocgenProviderUnavailableError
from app.db import models
from tests.helpers import FakeExecuteResult


def test_health_and_profile_read_write(client, auth_headers):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    created = client.post(
        "/api/v1/profiles",
        headers=auth_headers,
        json={
            "resume_text": "5 years Python",
            "title": "Python Developer",
            "full_name": "Smoke Candidate",
            "city": "Berlin",
        },
    )
    assert created.status_code == 201
    created_payload = created.json()
    profile_id = created_payload["id"]
    assert created_payload["full_name"] == "Smoke Candidate"

    updated = client.put(
        f"/api/v1/profiles/{profile_id}",
        headers=auth_headers,
        json={"title": "Senior Python Developer", "remote_ok": True},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Senior Python Developer"


def test_recommendations_endpoint_returns_expected_structure(client, fake_db, auth_headers):
    fake_db.queue_execute_results(
        FakeExecuteResult(
            all_value=[
                (
                    SimpleNamespace(final_score=0.83, verdict="strong"),
                    SimpleNamespace(
                        id=1,
                        title="Senior Backend Engineer",
                        company_name="Acme",
                        location="Remote",
                        url="https://example.com/vacancy/1",
                    ),
                )
            ]
        )
    )

    response = client.get("/api/v1/profiles/1/recommendations", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()

    assert payload["profile_id"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["verdict"] == "strong"
    assert "final_score" in payload["items"][0]


def test_tailoring_endpoint_returns_explanation_and_evidence(client, fake_db, monkeypatch, auth_headers):
    fake_db.queue_execute_results(
        FakeExecuteResult(scalar_value=SimpleNamespace(explanation={"summary": "Good fit"})),
        FakeExecuteResult(
            all_value=[
                SimpleNamespace(evidence_text="FastAPI project", confidence=0.9, evidence_type="project")
            ]
        ),
    )

    response = client.get("/api/v1/profiles/1/vacancies/1/tailoring", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()

    assert payload["profile_id"] == 1
    assert payload["vacancy_id"] == 1
    assert payload["explanation"] == {"summary": "Good fit"}
    assert payload["evidence"][0]["evidence_text"] == "FastAPI project"


def test_docgen_happy_path_and_approvals(client, monkeypatch, auth_headers):
    def _fake_resume_generate(self, profile_id: int, vacancy_id: int):
        return models.ResumeVersion(
            id=321,
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            title="AI resume draft",
            content_text="Generated resume draft",
            format="plain",
            source="ai",
            status="draft",
            created_at=datetime.now(timezone.utc),
            generation_metadata={"provider": "fake", "status": "draft"},
        )

    monkeypatch.setattr(
        "app.services.docgen.document_generation_service.DocumentGenerationService.generate_resume_draft",
        _fake_resume_generate,
    )

    generated = client.post("/api/v1/profiles/1/vacancies/1/resume/generate", headers=auth_headers)
    assert generated.status_code == 201
    draft_payload = generated.json()
    assert draft_payload["status"] == "draft"
    assert draft_payload["source"] == "ai"

    resume_created = client.post(
        "/api/v1/profiles/1/resume-versions",
        headers=auth_headers,
        json={"vacancy_id": 1, "content_text": "Draft resume from editor"},
    )
    assert resume_created.status_code == 201
    resume_id = resume_created.json()["id"]

    resume_approved = client.post(f"/api/v1/profiles/1/resume-versions/{resume_id}/approve", headers=auth_headers)
    assert resume_approved.status_code == 200
    assert resume_approved.json()["status"] == "approved"

    cover_created = client.post(
        "/api/v1/profiles/1/cover-letter-versions",
        headers=auth_headers,
        json={"vacancy_id": 1, "content_text": "Draft cover letter"},
    )
    assert cover_created.status_code == 201
    cover_id = cover_created.json()["id"]

    cover_approved = client.post(f"/api/v1/profiles/1/cover-letter-versions/{cover_id}/approve", headers=auth_headers)
    assert cover_approved.status_code == 200
    assert cover_approved.json()["status"] == "approved"


def test_docgen_provider_failure_is_normalized(client, monkeypatch, auth_headers):
    def _raise_provider_failure(self, profile_id: int, vacancy_id: int):
        raise DocgenProviderUnavailableError("provider unavailable in smoke test")

    monkeypatch.setattr(
        "app.services.docgen.document_generation_service.DocumentGenerationService.generate_cover_letter_draft",
        _raise_provider_failure,
    )

    response = client.post("/api/v1/profiles/1/vacancies/1/cover-letter/generate", headers=auth_headers)
    assert response.status_code == 503
    assert "provider unavailable" in response.json()["detail"]
