from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String, unique=True, nullable=False, index=True)
    document_type = Column(String, nullable=False)
    processing_status = Column(String, nullable=False)

    file_type = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)
    is_supported = Column(Boolean, nullable=True)
    is_readable = Column(Boolean, nullable=True)

    extracted_data = Column(JSONB, nullable=True)
    validation = Column(JSONB, nullable=True)
    processing_metadata = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )