from app.db import models


def test_create_application(client):
    response = client.post(
        "/api/v1/profiles/1/applications",
        json={"vacancy_id": 1, "status": "saved", "note": "High priority"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["profile_id"] == 1
    assert payload["vacancy_id"] == 1
    assert payload["status"] == "saved"
    assert payload["note"] == "High priority"


def test_change_status_writes_history(client):
    created = client.post("/api/v1/profiles/1/applications", json={"vacancy_id": 1})
    assert created.status_code == 201
    application_id = created.json()["id"]

    changed = client.post(
        f"/api/v1/profiles/1/applications/{application_id}/status",
        json={"status": "applied", "note": "Submitted via company website"},
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "applied"

    history_response = client.get(f"/api/v1/profiles/1/applications/{application_id}/history")
    assert history_response.status_code == 200

    history = history_response.json()
    assert len(history) == 2
    applied_item = next((item for item in history if item["to_status"] == "applied"), None)
    assert applied_item is not None
    assert applied_item["from_status"] == "saved"


def test_history_endpoint_returns_ordered_events(client):
    created = client.post("/api/v1/profiles/1/applications", json={"vacancy_id": 1})
    assert created.status_code == 201
    application_id = created.json()["id"]

    first_change = client.post(
        f"/api/v1/profiles/1/applications/{application_id}/status",
        json={"status": "planned", "note": "Planning the submit"},
    )
    assert first_change.status_code == 200

    second_change = client.post(
        f"/api/v1/profiles/1/applications/{application_id}/status",
        json={"status": "applied", "note": "Sent CV"},
    )
    assert second_change.status_code == 200

    history_response = client.get(f"/api/v1/profiles/1/applications/{application_id}/history")
    assert history_response.status_code == 200
    history = history_response.json()

    assert [item["to_status"] for item in history[:3]] == ["saved", "planned", "applied"]


def test_attach_document_validates_profile_ownership(client, fake_db):
    fake_db.add(
        models.ResumeVersion(
            profile_id=1,
            vacancy_id=1,
            title="Resume for vacancy",
            content_text="Owned by profile 1",
        )
    )
    fake_db.add(
        models.ResumeVersion(
            profile_id=2,
            vacancy_id=1,
            title="Foreign resume",
            content_text="Owned by another profile",
        )
    )

    created = client.post("/api/v1/profiles/1/applications", json={"vacancy_id": 1})
    assert created.status_code == 201
    application_id = created.json()["id"]

    valid_update = client.put(
        f"/api/v1/profiles/1/applications/{application_id}",
        json={"resume_version_id": 1},
    )
    assert valid_update.status_code == 200
    assert valid_update.json()["resume_version_id"] == 1

    invalid_update = client.put(
        f"/api/v1/profiles/1/applications/{application_id}",
        json={"resume_version_id": 2},
    )
    assert invalid_update.status_code == 400
    assert "another profile" in invalid_update.json()["detail"]
