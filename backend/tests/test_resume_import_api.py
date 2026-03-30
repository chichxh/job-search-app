from io import BytesIO
from pathlib import Path

from docx import Document

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "resume"


def _open_fixture(name: str, mode: str = "rb"):
    return (FIXTURES_DIR / name).open(mode)


def _build_docx_bytes(*lines: str) -> bytes:
    document = Document()
    for line in lines:
        document.add_paragraph(line)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_resume_extract_txt_happy_path(client, auth_headers):
    with _open_fixture("simple_resume.txt") as file_handle:
        response = client.post(
            "/api/v1/profiles/1/resume-import/extract",
            headers=auth_headers,
            files={"file": ("simple_resume.txt", file_handle, "text/plain")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detected_type"] == "txt"
    assert payload["extractor_used"] == "plain_text"
    assert payload["import_ready"] is True
    assert "John Doe" in payload["extracted_text"]
    assert payload["text_length"] > 20


def test_resume_extract_docx_happy_path(client, auth_headers):
    docx_bytes = _build_docx_bytes("Jane Candidate", "Python Developer", "FastAPI PostgreSQL Docker")

    response = client.post(
        "/api/v1/profiles/1/resume-import/extract",
        headers=auth_headers,
        files={
            "file": (
                "simple_resume.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detected_type"] == "docx"
    assert payload["extractor_used"] == "python-docx"
    assert "Jane Candidate" in payload["extracted_text"]


def test_resume_extract_pdf_happy_path(client, auth_headers):
    with _open_fixture("simple_resume.pdf") as file_handle:
        response = client.post(
            "/api/v1/profiles/1/resume-import/extract",
            headers=auth_headers,
            files={"file": ("simple_resume.pdf", file_handle, "application/pdf")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detected_type"] == "pdf"
    assert payload["extractor_used"] == "pypdf"
    assert "Alice Backend Engineer" in payload["extracted_text"]


def test_resume_extract_unsupported_type_returns_415(client, auth_headers):
    with _open_fixture("unsupported_sample.bin") as file_handle:
        response = client.post(
            "/api/v1/profiles/1/resume-import/extract",
            headers=auth_headers,
            files={"file": ("unsupported_sample.bin", file_handle, "application/octet-stream")},
        )

    assert response.status_code == 415


def test_resume_extract_near_empty_text_returns_422(client, auth_headers):
    response = client.post(
        "/api/v1/profiles/1/resume-import/extract",
        headers=auth_headers,
        files={"file": ("tiny.txt", b"hi", "text/plain")},
    )

    assert response.status_code == 422
    assert "too short" in response.json()["detail"].lower()


def test_resume_extract_blocks_foreign_profile(client, foreign_auth_headers):
    with _open_fixture("simple_resume.txt") as file_handle:
        response = client.post(
            "/api/v1/profiles/1/resume-import/extract",
            headers=foreign_auth_headers,
            files={"file": ("simple_resume.txt", file_handle, "text/plain")},
        )

    assert response.status_code == 404
