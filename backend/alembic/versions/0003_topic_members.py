"""Question membership (and per-question keywords) for each topic.

Revision ID: 0003_topic_members
Revises: 0002_table_cell_bboxes
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_topic_members"
down_revision: str | None = "0002_table_cell_bboxes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("members_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("topics", "members_json")
