import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ReportChangeKind, ReportStatus, ReportType
from app.services.report_history import describe


class UserSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_type: ReportType
    title: str
    status: ReportStatus
    content_json: dict
    org_unit_id: uuid.UUID
    created_by: uuid.UUID
    approver_id: uuid.UUID | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime


class ReportCreateIn(BaseModel):
    report_type: ReportType
    title: str = Field(min_length=1, max_length=500)
    content_json: dict = Field(default_factory=dict)
    due_date: date | None = None


class ReportUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content_json: dict | None = None
    due_date: date | None = None
    change_note: str | None = Field(default=None, max_length=500)


class RejectIn(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)


class ReportVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    content_json: dict
    editor: UserSummaryOut
    # What happened, as a code the frontend words in the reader's language (#71), and the
    # human comment exactly as typed. Rows from before #71 are mapped from change_note.
    change_kind: ReportChangeKind | None = None
    change_comment: str | None = None
    change_note: str | None = None  # legacy sentence, kept so no recorded history is lost
    created_at: datetime

    @model_validator(mode="after")
    def _kind_from_legacy_note(self) -> "ReportVersionOut":
        self.change_kind, self.change_comment = describe(
            self.change_kind, self.change_comment, self.change_note
        )
        return self
