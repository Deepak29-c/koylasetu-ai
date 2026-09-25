import uuid
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity, str_enum
from app.models.document import EMBED_DIM
from app.models.enums import House, QaRoute, QuestionType, ReportStatus, ReportType


class ParliamentQuestion(Entity):
    """Past + new PQs. Past ones are the benchmark and the topic-model source."""

    __tablename__ = "parliament_questions"

    house: Mapped[House] = mapped_column(str_enum(House, "house"))
    q_type: Mapped[QuestionType] = mapped_column(str_enum(QuestionType, "question_type"))
    q_no: Mapped[str | None] = mapped_column(String(16))
    answer_date: Mapped[date | None] = mapped_column(Date, index=True)
    mp_name: Mapped[str | None] = mapped_column(String(300))
    subject: Mapped[str | None] = mapped_column(String(500))
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str | None] = mapped_column(Text)  # official answer, if known
    parts_json: Mapped[list | None] = mapped_column(JSONB)  # [{"label": "a", "text": "..."}]
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    # For the "similar past questions" panel (guide 10.2).
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


class Report(Entity):
    __tablename__ = "reports"

    report_type: Mapped[ReportType] = mapped_column(str_enum(ReportType, "report_type"))
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[ReportStatus] = mapped_column(
        str_enum(ReportStatus, "report_status"), default=ReportStatus.DRAFT, index=True
    )
    content_json: Mapped[dict] = mapped_column(JSONB, default=dict)  # editor blocks
    pq_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parliament_questions.id")
    )
    org_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    due_date: Mapped[date | None] = mapped_column(Date)


class ReportVersion(Entity):
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("report_id", "version"),)

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    content_json: Mapped[dict] = mapped_column(JSONB)
    edited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    change_note: Mapped[str | None] = mapped_column(Text)


class ReportCitation(Entity):
    """Links every figure in a report to its source fact or chunk."""

    __tablename__ = "report_citations"
    __table_args__ = (
        CheckConstraint("fact_id IS NOT NULL OR chunk_id IS NOT NULL", name="has_source"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    fact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("facts.id"))
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chunks.id"))
    location_in_report: Mapped[str] = mapped_column(String(200))  # block id + offset


class QaLog(Entity):
    __tablename__ = "qa_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    route: Mapped[QaRoute | None] = mapped_column(str_enum(QaRoute, "qa_route"))
    sql: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    citations_json: Mapped[list | None] = mapped_column(JSONB)
    grounded: Mapped[bool | None] = mapped_column(Boolean)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[dict | None] = mapped_column(JSONB)  # {"score": 1 | -1, "comment": "..."}


class Topic(Entity):
    __tablename__ = "topics"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    topic_no: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(300))
    keywords: Mapped[list] = mapped_column(JSONB)
    size: Mapped[int] = mapped_column(Integer)
    period_counts_json: Mapped[dict | None] = mapped_column(JSONB)


class AuditLog(Entity):
    __tablename__ = "audit_log"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(50), index=True)  # login, upload, review, ...
    entity: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details_json: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
