import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import DocType, DocumentStatus, FactStatus, Metric, PeriodType
from app.services import failures


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
    page_count: int | None
    pages_done: int
    source_url: str | None
    created_at: datetime
    # Read from the row but never sent: the raw exception text and the server path (#70).
    error_message: str | None = Field(default=None, exclude=True)
    file_path: str | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_missing(self) -> bool:
        """The original file is no longer on disk, so its pages cannot be shown (#69). The
        list says so before anyone clicks; processed text and figures are unaffected."""
        return self.file_path is not None and failures.original_is_missing(self.file_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failure_reason(self) -> failures.FailureReason | None:
        """Why processing failed, as a code the frontend shows in the user's language. A
        missing original is reported whatever the status, so the fix (upload it again) is
        visible on the list."""
        if self.status == DocumentStatus.FAILED:
            return failures.reason_from_record(self.error_message) or "unknown"
        return "file_missing" if self.file_missing else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failure_message(self) -> str | None:
        """The same reason as a plain English sentence, for API clients."""
        reason = self.failure_reason
        return failures.MESSAGES[reason] if reason else None


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    bbox: list[float] | None
    has_embedding: bool


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    table_title: str | None
    bbox: list[float] | None
    rows_json: list[list[str]]
    cell_bboxes: list[list[list[float] | None]] | None = None


class PageOut(BaseModel):
    """One page for the document viewer: text chunks and tables with highlight boxes."""

    document_id: uuid.UUID
    document_title: str
    source_url: str | None
    page_no: int
    page_count: int | None
    has_text_layer: bool
    ocr_used: bool
    ocr_confidence: float | None
    # Size of the coordinate space the bboxes use: PDF points for PDFs, pixels for images.
    width: float | None
    height: float | None
    image_url: str | None
    chunks: list[ChunkOut]
    tables: list[TableOut]


class FactOut(BaseModel):
    """One number pulled from a table, with where it came from (document, page, cell box)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric: Metric
    subsidiary: str | None
    state: str | None
    period_type: PeriodType | None
    period: str | None
    category: str | None
    value_raw: str
    value: float
    unit: str | None  # None: the table did not say; value_std assumes the standard unit
    value_std: float | None
    status: FactStatus
    confidence: float
    page_no: int
    bbox: list[float] | None
    table_id: uuid.UUID | None


class UploadResult(BaseModel):
    filename: str
    result: Literal["created", "duplicate", "rejected"]
    document: DocumentOut | None = None
    queued: bool = False
    error: str | None = None
