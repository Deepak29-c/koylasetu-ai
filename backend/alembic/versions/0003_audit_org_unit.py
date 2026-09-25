"""Give audit_log an org unit, so the audit list scopes like every other list.

Revision ID: 0003_audit_org_unit
Revises: 0002_table_cell_bboxes
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_audit_org_unit"
down_revision: str | None = "0002_table_cell_bboxes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_log",
        sa.Column("org_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_audit_log_org_unit_id_org_units", "audit_log", "org_units", ["org_unit_id"], ["id"]
    )
    op.create_index("ix_audit_log_org_unit_id", "audit_log", ["org_unit_id"])
    # Existing rows: attribute each to the actor's current unit. Rows with no actor
    # (system actions, failed logins on unknown emails) stay null and remain HQ-only.
    op.execute(
        "UPDATE audit_log SET org_unit_id = users.org_unit_id "
        "FROM users WHERE audit_log.user_id = users.id"
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_org_unit_id", table_name="audit_log")
    op.drop_constraint("fk_audit_log_org_unit_id_org_units", "audit_log", type_="foreignkey")
    op.drop_column("audit_log", "org_unit_id")
