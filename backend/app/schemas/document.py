from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    document_name: str
    document_type: str


class DocumentResponse(DocumentBase):
    id: int
    processing_status: str
    file_type: str | None = None
    page_count: int | None = None
    is_supported: bool | None = None
    is_readable: bool | None = None
    extracted_data: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    processing_metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    processed_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)