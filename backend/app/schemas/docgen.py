from typing import Literal, Optional

from pydantic import BaseModel

from app.schemas.cover_letter_version import CoverLetterVersionRead
from app.schemas.resume_version import ResumeVersionRead


class DocumentByTaskResponse(BaseModel):
    task_id: str
    state: str
    document_type: Literal["resume", "cover_letter"]
    resume_version: Optional[ResumeVersionRead] = None
    cover_letter_version: Optional[CoverLetterVersionRead] = None
