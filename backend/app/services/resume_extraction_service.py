from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re

from docx import Document
from pypdf import PdfReader
from striprtf.striprtf import rtf_to_text


MAX_RESUME_FILE_SIZE_BYTES = 5 * 1024 * 1024
_MIN_MEANINGFUL_TEXT_LENGTH = 20
_ALLOWED_TYPES = {"txt", "md", "docx", "pdf", "rtf"}
_EXTENSION_TO_TYPE = {
    ".txt": "txt",
    ".md": "md",
    ".docx": "docx",
    ".pdf": "pdf",
    ".rtf": "rtf",
}

_MIME_TO_TYPE = {
    "text/plain": "txt",
    "text/markdown": "md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/pdf": "pdf",
    "application/rtf": "rtf",
    "text/rtf": "rtf",
}


class ResumeExtractionError(Exception):
    pass


class UnsupportedResumeFileTypeError(ResumeExtractionError):
    pass


class EmptyResumeFileError(ResumeExtractionError):
    pass


class ResumeFileTooLargeError(ResumeExtractionError):
    pass


class ResumeExtractionFailedError(ResumeExtractionError):
    pass


class ResumeNoTextExtractedError(ResumeExtractionError):
    pass


@dataclass(slots=True)
class ResumeExtractionResult:
    filename: str
    content_type: str | None
    detected_type: str
    extracted_text: str
    text_length: int
    warnings: list[str]
    extractor_used: str
    import_ready: bool


class ResumeExtractionService:
    def extract(self, *, filename: str, content_type: str | None, content: bytes) -> ResumeExtractionResult:
        if not content:
            raise EmptyResumeFileError("Uploaded file is empty")

        if len(content) > MAX_RESUME_FILE_SIZE_BYTES:
            raise ResumeFileTooLargeError(
                f"Uploaded file is too large (max {MAX_RESUME_FILE_SIZE_BYTES // (1024 * 1024)} MB)"
            )

        detected_type = self._detect_type(filename=filename, content_type=content_type)
        warnings: list[str] = []

        if detected_type in {"txt", "md"}:
            extracted = self._extract_plain_text(content)
            extractor_used = "plain_text"
        elif detected_type == "docx":
            extracted = self._extract_docx_text(content)
            extractor_used = "python-docx"
        elif detected_type == "pdf":
            extracted = self._extract_pdf_text(content)
            extractor_used = "pypdf"
        elif detected_type == "rtf":
            extracted = self._extract_rtf_text(content)
            extractor_used = "striprtf"
        else:
            raise UnsupportedResumeFileTypeError("Unsupported resume file type")

        normalized = self._normalize_text(extracted)
        text_length = len(normalized)

        if not normalized:
            if detected_type == "pdf":
                raise ResumeNoTextExtractedError("PDF has no extractable text (image-only/scanned PDF is not supported)")
            raise ResumeNoTextExtractedError("No extractable text found in uploaded file")

        import_ready = text_length >= _MIN_MEANINGFUL_TEXT_LENGTH
        if not import_ready:
            warnings.append("Extracted text is too short to be import-ready")

        return ResumeExtractionResult(
            filename=filename,
            content_type=content_type,
            detected_type=detected_type,
            extracted_text=normalized,
            text_length=text_length,
            warnings=warnings,
            extractor_used=extractor_used,
            import_ready=import_ready,
        )

    def _detect_type(self, *, filename: str, content_type: str | None) -> str:
        ext = ""
        if "." in filename:
            ext = f".{filename.rsplit('.', 1)[-1].lower()}"
        by_ext = _EXTENSION_TO_TYPE.get(ext)
        by_mime = _MIME_TO_TYPE.get((content_type or "").lower())

        detected = by_ext or by_mime
        if not detected or detected not in _ALLOWED_TYPES:
            raise UnsupportedResumeFileTypeError(
                "Unsupported file type. Supported formats: .txt, .md, .docx, .pdf (text-based), .rtf"
            )

        return detected

    @staticmethod
    def _extract_plain_text(content: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ResumeExtractionFailedError("Failed to decode text file")

    @staticmethod
    def _extract_docx_text(content: bytes) -> str:
        try:
            document = Document(BytesIO(content))
        except Exception as exc:
            raise ResumeExtractionFailedError("Failed to read DOCX file") from exc

        blocks = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
        return "\n".join(blocks)

    @staticmethod
    def _extract_pdf_text(content: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise ResumeExtractionFailedError("Failed to read PDF file") from exc

        chunks: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text:
                chunks.append(text)
        return "\n".join(chunks)

    @staticmethod
    def _extract_rtf_text(content: bytes) -> str:
        decoded = ResumeExtractionService._extract_plain_text(content)
        try:
            return rtf_to_text(decoded)
        except Exception as exc:
            raise ResumeExtractionFailedError("Failed to read RTF file") from exc

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.replace("\x00", "")
        normalized = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        normalized = re.sub(r"[ \t]{2,}", " ", normalized)
        return normalized.strip()
