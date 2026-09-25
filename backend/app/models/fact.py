import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity, str_enum
from app.models.enums import FactStatus, IssueStatus, Metric, PeriodType, ReviewAction, Severity


class Fact(Entity):
    """Every number in the system, with its source (document, page, bbox)."""

    __tablename__ = "facts"
    __table_args__ = (Index("ix_facts_lookup", "metric", "subsidiary", "period"),)

    metric: Mapped[Metric] = mapped_column(str_enum(Metric, "metric"))
    subsidiary: Mapped[str | None] = mapped_column(String(16))  # ECL, ..., CIL, SCCL, CAPTIVE
    coalfield: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    period_type: Mapped[PeriodType | None] = mapped_column(str_enum(PeriodType, "period_type"))
    period: Mapped[str | None] = mapped_column(String(16))  # "FY 2023-24" or "2024-12"
    value_raw: Mapped[str] = mapped_column(String(64))  # the cell text exactly as in the source
    value: Mapped[float] = mapped_column(Numeric)  # parsed, in the original unit
    unit: Mapped[str | None] = mapped_column(String(32))  # original unit
    value_std: Mapped[float | None] = mapped_column(Numeric)  # in the metric's standard unit
    # Measured / Indicated / Inferred / Total, optionally "· Coking" for one coal type
    category: Mapped[str | None] = mapped_column(String(64))
    # Row and column headers the value was read under, e.g. "NCL · Production during Dec / FY 25"
    label: Mapped[str | None] = mapped_column(Text)
    status: Mapped[FactStatus] = mapped_column(
        str_enum(FactStatus, "fact_status"), default=FactStatus.EXTRACTED, index=True
    )
    confidence: Mapped[float] = mapped_column(Float)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_no: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[list[float] | None] = mapped_column(JSONB)
    table_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extracted_tables.id", ondelete="SET NULL")
    )


class ValidationIssue(Entity):
    __tablename__ = "validation_issues"

    fact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facts.id", ondelete="CASCADE"), index=True
    )
    rule_code: Mapped[str] = mapped_column(String(8))  # V01..V08
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(str_enum(Severity, "severity"))
    related_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facts.id", ondelete="SET NULL")
    )
    status: Mapped[IssueStatus] = mapped_column(
        str_enum(IssueStatus, "issue_status"), default=IssueStatus.OPEN, index=True
    )


class ReviewActionLog(Entity):
    __tablename__ = "review_actions"

    fact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[ReviewAction] = mapped_column(str_enum(ReviewAction, "review_action"))
    old_value: Mapped[str | None] = mapped_column(String(64))
    new_value: Mapped[str | None] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(Text)
