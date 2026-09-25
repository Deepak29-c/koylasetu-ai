import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric: str
    subsidiary: str | None
    state: str | None
    category: str | None
    period_type: str | None
    period: str | None
    value_raw: str
    value: float
    unit: str | None
    value_std: float | None
    status: str
    confidence: float
    document_id: uuid.UUID
    page_no: int
    bbox: list[float] | None
    label: str | None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_code: str
    message: str
    severity: str
    status: str


class RelatedFactOut(FactOut):
    document_title: str


class ReviewItem(BaseModel):
    """One flagged fact with every open issue on it: one row of the review queue."""

    fact: FactOut
    document_title: str
    issues: list[IssueOut]
    related: list[RelatedFactOut]
    worst_severity: str
    created_at: datetime


class DecidedItem(BaseModel):
    """A fact a reviewer already decided, with its latest decision, so it can be changed."""

    fact: FactOut
    document_title: str
    issues: list[IssueOut]  # why it was flagged (now resolved)
    related: list[RelatedFactOut]
    action: str  # latest decision: ACCEPT / EDIT / REJECT
    comment: str | None
    decided_by: str
    decided_at: datetime
    decisions: int  # how many times this fact was decided


class ReviewDecision(BaseModel):
    action: Literal["ACCEPT", "EDIT", "REJECT"]
    new_value: str | None = Field(default=None, max_length=64)
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def rules(self) -> "ReviewDecision":
        # guide W2: a comment is optional for Accept and required for Edit / Reject
        if self.action in ("EDIT", "REJECT") and not (self.comment and self.comment.strip()):
            raise ValueError("A comment is required to edit or reject a value")
        if self.action == "EDIT" and not (self.new_value and self.new_value.strip()):
            raise ValueError("Type the correct value")
        return self


class ReviewSummary(BaseModel):
    total_facts: int
    auto_verified: int
    flagged: int
    reviewed_verified: int
    rejected: int
    automation_percent: float | None  # auto-accepted / all facts (problem statement metric)
