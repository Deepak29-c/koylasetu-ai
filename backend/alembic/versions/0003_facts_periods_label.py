"""Facts: YTD and AS_ON period types, source label, longer category.

Revision ID: 0003_facts_periods_label
Revises: 0002_table_cell_bboxes
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_facts_periods_label"
down_revision: str | None = "0002_table_cell_bboxes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "period_type IN ('FY', 'MONTH')"
NEW = "period_type IN ('FY', 'MONTH', 'YTD', 'AS_ON')"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_facts_period_type"), "facts", type_="check")
    op.create_check_constraint(op.f("ck_facts_period_type"), "facts", NEW)
    op.add_column("facts", sa.Column("label", sa.Text(), nullable=True))
    op.alter_column("facts", "category", type_=sa.String(64), existing_type=sa.String(32))


def downgrade() -> None:
    op.alter_column("facts", "category", type_=sa.String(32), existing_type=sa.String(64))
    op.drop_column("facts", "label")
    op.execute("DELETE FROM facts WHERE period_type IN ('YTD', 'AS_ON')")
    op.drop_constraint(op.f("ck_facts_period_type"), "facts", type_="check")
    op.create_check_constraint(op.f("ck_facts_period_type"), "facts", OLD)
