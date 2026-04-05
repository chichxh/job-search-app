from app.tasks.observability import failure_summary
from app.utils.log_safety import sanitize_for_log, summarize_hh_import_params


def test_sanitize_for_log_redacts_sensitive_fields_and_pii() -> None:
    payload = {
        "resume_text": "Senior python dev",
        "email": "person@example.com",
        "phone": "+1 (555) 123-45-67",
        "nested": {"auth_token": "secret-token", "note": "contact me at foo@bar.com"},
    }

    sanitized = sanitize_for_log(payload)

    assert sanitized["resume_text"] == "[redacted]"
    assert sanitized["email"] == "[redacted]"
    assert sanitized["phone"] == "[redacted]"
    assert sanitized["nested"]["auth_token"] == "[redacted]"
    assert "foo@bar.com" not in sanitized["nested"]["note"]


def test_summarize_hh_import_params_does_not_expose_raw_text() -> None:
    params = {
        "text": "Data Engineer anna@example.com +7 999 555-11-22",
        "area": "1",
        "per_page": 30,
        "extra_params": {"professional_role": [96], "search_field": "name"},
    }

    summary = summarize_hh_import_params(params)

    assert "text" not in summary
    assert summary["text_len"] == len(params["text"])
    assert summary["extra_params_keys"] == ["professional_role", "search_field"]


def test_failure_summary_masks_email_and_phone() -> None:
    err = ValueError("failed for anna@example.com, call +1 212 333 4444")

    summary = failure_summary(err)

    assert "anna@example.com" not in summary
    assert "212 333 4444" not in summary
    assert "ValueError" in summary


def test_sanitize_for_log_redacts_session_and_content_payloads() -> None:
    payload = {
        "cookies": [{"name": "sid", "value": "secret-cookie"}],
        "storage_state": {"origins": [{"origin": "https://hh.ru", "localStorage": [{"name": "token", "value": "abc"}]}]},
        "session_state_ref": "local://hh-browser-session/session_abc123.json",
        "cover_letter_text": "Full cover letter text should never be logged",
        "raw_resume_text": "Very long raw resume text",
    }

    sanitized = sanitize_for_log(payload)

    assert sanitized["cookies"] == "[redacted]"
    assert sanitized["storage_state"] == "[redacted]"
    assert sanitized["session_state_ref"] == "[redacted]"
    assert sanitized["cover_letter_text"] == "[redacted]"
    assert sanitized["raw_resume_text"] == "[redacted]"
