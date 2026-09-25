import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReportStatus, ReportType


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
    change_note: str | None
    created_at: datetime
