import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocType, DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    original_filename: str
    doc_type: DocType
    fy: str | None
    org_unit_id: uuid.UUID
    is_public: bool
    language: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    page_count: int | None
    pages_done: int
    source_url: str | None
    created_at: datetime


class UploadResult(BaseModel):
    filename: str
    result: Literal["created", "duplicate", "rejected"]
    document: DocumentOut | None = None
    queued: bool = False
    error: str | None = None
