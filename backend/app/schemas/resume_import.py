from pydantic import BaseModel, Field


class ResumeExtractionResponse(BaseModel):
    filename: str
    content_type: str | None = None
    detected_type: str = Field(description="Normalized detected file type")
    extracted_text: str
    text_length: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    extractor_used: str
    import_ready: bool
