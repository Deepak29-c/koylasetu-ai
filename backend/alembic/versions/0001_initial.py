"""Initial schema: all tables from developer guide section 6.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "org_units",
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "subsidiary",
                "hq",
                "ministry",
                name="org_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_org_units")),
        sa.UniqueConstraint("code", name=op.f("uq_org_units_code")),
    )
    op.create_table(
        "topics",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("topic_no", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("period_counts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topics")),
    )
    op.create_index(op.f("ix_topics_run_id"), "topics", ["run_id"], unique=False)
    op.create_table(
        "users",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("roles", sa.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("org_unit_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_units.id"], name=op.f("fk_users_org_unit_id_org_units")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "audit_log",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_audit_log_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"], unique=False)
    op.create_table(
        "documents",
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column(
            "doc_type",
            sa.Enum(
                "annual_report",
                "coal_inventory",
                "monthly_stats",
                "pq_answer",
                "other",
                name="doc_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("fy", sa.String(length=16), nullable=True),
        sa.Column("org_unit_id", sa.UUID(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "UPLOADED",
                "PROCESSING",
                "PROCESSED",
                "NEEDS_REVIEW",
                "FAILED",
                name="document_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("pages_done", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_units.id"], name=op.f("fk_documents_org_unit_id_org_units")
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name=op.f("fk_documents_uploaded_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("sha256", name=op.f("uq_documents_sha256")),
    )
    op.create_index(op.f("ix_documents_org_unit_id"), "documents", ["org_unit_id"], unique=False)
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)
    op.create_table(
        "qa_logs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "route",
            sa.Enum(
                "NUMERIC",
                "TEXTUAL",
                "MIXED",
                name="qa_route",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("sql", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("citations_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("feedback", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_qa_logs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_qa_logs")),
    )
    op.create_index(op.f("ix_qa_logs_user_id"), "qa_logs", ["user_id"], unique=False)
    op.create_table(
        "chunks",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', text)", persisted=True),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunks")),
    )
    op.create_index(op.f("ix_chunks_document_id"), "chunks", ["document_id"], unique=False)
    op.create_index(
        "ix_chunks_embedding",
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], unique=False, postgresql_using="gin")
    op.create_table(
        "extracted_tables",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rows_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("table_title", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_extracted_tables_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extracted_tables")),
    )
    op.create_index(
        op.f("ix_extracted_tables_document_id"), "extracted_tables", ["document_id"], unique=False
    )
    op.create_table(
        "pages",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("has_text_layer", sa.Boolean(), nullable=False),
        sa.Column("ocr_used", sa.Boolean(), nullable=False),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("image_path", sa.String(length=1000), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_pages_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages")),
        sa.UniqueConstraint("document_id", "page_no", name=op.f("uq_pages_document_id")),
    )
    op.create_table(
        "parliament_questions",
        sa.Column(
            "house",
            sa.Enum("LS", "RS", name="house", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column(
            "q_type",
            sa.Enum(
                "starred",
                "unstarred",
                name="question_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("q_no", sa.String(length=16), nullable=True),
        sa.Column("answer_date", sa.Date(), nullable=True),
        sa.Column("mp_name", sa.String(length=300), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("parts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_parliament_questions_document_id_documents"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parliament_questions")),
    )
    op.create_index(
        op.f("ix_parliament_questions_answer_date"),
        "parliament_questions",
        ["answer_date"],
        unique=False,
    )
    op.create_table(
        "facts",
        sa.Column(
            "metric",
            sa.Enum(
                "coal_production",
                "coal_offtake",
                "ob_removal",
                "production_target",
                "coking_coal_production",
                "coal_resource",
                "coal_import",
                name="metric",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("subsidiary", sa.String(length=16), nullable=True),
        sa.Column("coalfield", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column(
            "period_type",
            sa.Enum(
                "FY",
                "MONTH",
                name="period_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("period", sa.String(length=16), nullable=True),
        sa.Column("value_raw", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("value_std", sa.Numeric(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "EXTRACTED",
                "FLAGGED",
                "VERIFIED",
                "REJECTED",
                name="fact_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("table_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_facts_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["table_id"],
            ["extracted_tables.id"],
            name=op.f("fk_facts_table_id_extracted_tables"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facts")),
    )
    op.create_index(op.f("ix_facts_document_id"), "facts", ["document_id"], unique=False)
    op.create_index("ix_facts_lookup", "facts", ["metric", "subsidiary", "period"], unique=False)
    op.create_index(op.f("ix_facts_status"), "facts", ["status"], unique=False)
    op.create_table(
        "reports",
        sa.Column(
            "report_type",
            sa.Enum(
                "pq_reply",
                "monthly",
                "briefing",
                name="report_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "IN_REVIEW",
                "RETURNED",
                "APPROVED",
                "EXPORTED",
                name="report_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pq_id", sa.UUID(), nullable=True),
        sa.Column("org_unit_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("approver_id", sa.UUID(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["approver_id"], ["users.id"], name=op.f("fk_reports_approver_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_reports_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"], ["org_units.id"], name=op.f("fk_reports_org_unit_id_org_units")
        ),
        sa.ForeignKeyConstraint(
            ["pq_id"],
            ["parliament_questions.id"],
            name=op.f("fk_reports_pq_id_parliament_questions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(op.f("ix_reports_org_unit_id"), "reports", ["org_unit_id"], unique=False)
    op.create_index(op.f("ix_reports_status"), "reports", ["status"], unique=False)
    op.create_table(
        "report_citations",
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("fact_id", sa.UUID(), nullable=True),
        sa.Column("chunk_id", sa.UUID(), nullable=True),
        sa.Column("location_in_report", sa.String(length=200), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fact_id IS NOT NULL OR chunk_id IS NOT NULL",
            name=op.f("ck_report_citations_has_source"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["chunks.id"], name=op.f("fk_report_citations_chunk_id_chunks")
        ),
        sa.ForeignKeyConstraint(
            ["fact_id"], ["facts.id"], name=op.f("fk_report_citations_fact_id_facts")
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name=op.f("fk_report_citations_report_id_reports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_citations")),
    )
    op.create_index(
        op.f("ix_report_citations_report_id"), "report_citations", ["report_id"], unique=False
    )
    op.create_table(
        "report_versions",
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edited_by", sa.UUID(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["edited_by"], ["users.id"], name=op.f("fk_report_versions_edited_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name=op.f("fk_report_versions_report_id_reports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_versions")),
        sa.UniqueConstraint("report_id", "version", name=op.f("uq_report_versions_report_id")),
    )
    op.create_table(
        "review_actions",
        sa.Column("fact_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "ACCEPT",
                "EDIT",
                "REJECT",
                name="review_action",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("old_value", sa.String(length=64), nullable=True),
        sa.Column("new_value", sa.String(length=64), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["fact_id"],
            ["facts.id"],
            name=op.f("fk_review_actions_fact_id_facts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_review_actions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_actions")),
    )
    op.create_index(op.f("ix_review_actions_fact_id"), "review_actions", ["fact_id"], unique=False)
    op.create_table(
        "validation_issues",
        sa.Column("fact_id", sa.UUID(), nullable=False),
        sa.Column("rule_code", sa.String(length=8), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "high",
                "medium",
                "low",
                name="severity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("related_fact_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "RESOLVED",
                name="issue_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["fact_id"],
            ["facts.id"],
            name=op.f("fk_validation_issues_fact_id_facts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["related_fact_id"],
            ["facts.id"],
            name=op.f("fk_validation_issues_related_fact_id_facts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validation_issues")),
    )
    op.create_index(
        op.f("ix_validation_issues_fact_id"), "validation_issues", ["fact_id"], unique=False
    )
    op.create_index(
        op.f("ix_validation_issues_status"), "validation_issues", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_table("validation_issues")
    op.drop_table("review_actions")
    op.drop_table("report_versions")
    op.drop_table("report_citations")
    op.drop_table("reports")
    op.drop_table("facts")
    op.drop_table("parliament_questions")
    op.drop_table("pages")
    op.drop_table("extracted_tables")
    op.drop_table("chunks")
    op.drop_table("qa_logs")
    op.drop_table("documents")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("topics")
    op.drop_table("org_units")
