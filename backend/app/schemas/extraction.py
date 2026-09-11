from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source_text: str | None = None
    page_number: int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExtractedField(BaseModel):
    value: Any = None
    evidence: Evidence | None = None


class ExtractionResult(BaseModel):
    document_type: str
    fields: dict[str, ExtractedField] = {}
    tables: list[dict[str, Any]] = []