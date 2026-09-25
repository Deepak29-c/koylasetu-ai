"""Rejoin the two 0003 revisions written in parallel (#51 audit scoping, #50 topics).

Both named 0002_table_cell_bboxes as their parent, which forked the revision chain and
made `alembic upgrade head` fail with "Multiple head revisions are present". Nothing
needs rewriting — this is the merge point alembic expects, and it changes no schema.

Revision ID: 0004_merge_heads
Revises: 0003_audit_org_unit, 0003_topic_members
Create Date: 2026-09-26
"""

from collections.abc import Sequence

revision: str = "0004_merge_heads"
down_revision: tuple[str, str] = ("0003_audit_org_unit", "0003_topic_members")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Nothing to do: both parents already made their changes."""


def downgrade() -> None:
    """Nothing to undo."""
