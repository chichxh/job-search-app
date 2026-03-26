from datetime import datetime, timezone

from app.db import models


def test_user_cannot_read_or_update_foreign_profile(client, foreign_auth_headers):
    foreign_read = client.get("/api/v1/profiles/1", headers=foreign_auth_headers)
    assert foreign_read.status_code == 404

    foreign_update = client.put(
        "/api/v1/profiles/1",
        json={"title": "hijacked"},
        headers=foreign_auth_headers,
    )
    assert foreign_update.status_code == 404


def test_user_cannot_edit_approve_or_delete_foreign_documents(client, fake_db, auth_headers, foreign_auth_headers):
    resume = models.ResumeVersion(profile_id=1, vacancy_id=1, content_text="owned resume")
    cover = models.CoverLetterVersion(profile_id=1, vacancy_id=1, content_text="owned cover")
    fake_db.add(resume)
    fake_db.add(cover)

    resume_update = client.put(
        f"/api/v1/profiles/1/resume-versions/{resume.id}",
        json={"content_text": "intrusion"},
        headers=foreign_auth_headers,
    )
    assert resume_update.status_code == 404

    resume_approve = client.post(
        f"/api/v1/profiles/1/resume-versions/{resume.id}/approve",
        headers=foreign_auth_headers,
    )
    assert resume_approve.status_code == 404

    cover_delete = client.delete(
        f"/api/v1/profiles/1/cover-letter-versions/{cover.id}",
        headers=foreign_auth_headers,
    )
    assert cover_delete.status_code == 404



def test_user_cannot_modify_foreign_application(client, fake_db, auth_headers, foreign_auth_headers):
    created = client.post(
        "/api/v1/profiles/1/applications",
        json={"vacancy_id": 1, "status": "saved"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    application_id = created.json()["id"]

    update = client.put(
        f"/api/v1/profiles/1/applications/{application_id}",
        json={"note": "stolen"},
        headers=foreign_auth_headers,
    )
    assert update.status_code == 404

    delete = client.delete(
        f"/api/v1/profiles/1/applications/{application_id}",
        headers=foreign_auth_headers,
    )
    assert delete.status_code == 404



def test_matching_and_docgen_block_foreign_profile_access(client, fake_db, foreign_auth_headers, monkeypatch):
    recommendations = client.get("/api/v1/profiles/1/recommendations", headers=foreign_auth_headers)
    assert recommendations.status_code == 404

    tailoring = client.get("/api/v1/profiles/1/vacancies/1/tailoring", headers=foreign_auth_headers)
    assert tailoring.status_code == 404

    def _fake_resume_generate(self, profile_id: int, vacancy_id: int):
        return models.ResumeVersion(
            id=99,
            profile_id=profile_id,
            vacancy_id=vacancy_id,
            title="AI draft",
            content_text="x",
            format="plain",
            source="ai",
            status="draft",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(
        "app.services.docgen.document_generation_service.DocumentGenerationService.generate_resume_draft",
        _fake_resume_generate,
    )

    docgen = client.post("/api/v1/profiles/1/vacancies/1/resume/generate", headers=foreign_auth_headers)
    assert docgen.status_code == 404
