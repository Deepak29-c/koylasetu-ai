"""Depth-wise coal resources by state (#97): one row per printed line of the inventory's
state-wise, depth-wise table.

Revision ID: 0008_depth_resources
Revises: 0007_report_version_change_kind
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_depth_resources"
down_revision: str | None = "0007_report_version_change_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "depth_resources",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(), nullable=True),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("section", sa.String(length=16), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("coal_type", sa.String(length=32), nullable=True),
        sa.Column("depth_range", sa.String(length=16), nullable=False),
        sa.Column("is_total", sa.Boolean(), nullable=False),
        sa.Column("measured", sa.Numeric(), nullable=False),
        sa.Column("indicated", sa.Numeric(), nullable=False),
        sa.Column("inferred", sa.Numeric(), nullable=False),
        sa.Column("total", sa.Numeric(), nullable=False),
        sa.Column("values_raw", postgresql.JSONB(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_depth_resources_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_depth_resources")),
    )
    op.create_index(
        op.f("ix_depth_resources_document_id"), "depth_resources", ["document_id"], unique=False
    )
    op.create_index("ix_depth_resources_lookup", "depth_resources", ["state", "period"])


def downgrade() -> None:
    op.drop_index("ix_depth_resources_lookup", table_name="depth_resources")
    op.drop_index(op.f("ix_depth_resources_document_id"), table_name="depth_resources")
    op.drop_table("depth_resources")
