"""A file is unique within a unit, not across the whole system.

Two units may each hold the same public circular. Before this, the second one to
upload it was told "This exact file was uploaded before" with nothing to open and no
copy of their own - see issue #44. The bytes are not duplicated: storage is
content-addressed by sha256, so both rows point at the same file on disk.

Revision ID: 0006_documents_unique_per_unit
Revises: 0005_facts_periods_label
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_documents_unique_per_unit"
down_revision: str | None = "0005_facts_periods_label"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_documents_sha256", "documents", type_="unique")
    op.create_index("ix_documents_sha256", "documents", ["sha256"])
    op.create_unique_constraint("uq_documents_org_unit_id", "documents", ["org_unit_id", "sha256"])


def downgrade() -> None:
    # Only reversible while no two units hold the same file.
    op.drop_constraint("uq_documents_org_unit_id", "documents", type_="unique")
    op.drop_index("ix_documents_sha256", table_name="documents")
    op.create_unique_constraint("uq_documents_sha256", "documents", ["sha256"])
