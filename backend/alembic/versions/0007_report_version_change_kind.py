"""Report versions: store what happened as a code, and the human comment separately.

Before this, `change_note` held English sentences ("Created", "Returned: <comment>"), so
version history stayed English in Hindi - see issue #71. `change_note` is kept untouched;
the known sentences are copied into the new columns so old rows read like new ones.

Revision ID: 0007_report_version_change_kind
Revises: 0006_documents_unique_per_unit
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_report_version_change_kind"
down_revision: str | None = "0006_documents_unique_per_unit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The sentences the API wrote before this revision, and the code each one means.
SENTENCES = {
    "Created": "created",
    "Approved": "approved",
    "First draft generated": "drafted",
    "First draft generated from the question": "drafted_from_question",
}
RETURNED = "Returned: "

rv = sa.table(
    "report_versions",
    sa.column("change_note", sa.Text),
    sa.column("change_kind", sa.String),
    sa.column("change_comment", sa.Text),
)


def upgrade() -> None:
    op.add_column("report_versions", sa.Column("change_kind", sa.String(32), nullable=True))
    op.add_column("report_versions", sa.Column("change_comment", sa.Text(), nullable=True))
    for sentence, kind in SENTENCES.items():
        op.execute(rv.update().where(rv.c.change_note == sentence).values(change_kind=kind))
    op.execute(
        rv.update()
        .where(rv.c.change_kind.is_(None), rv.c.change_note.like(RETURNED + "%"))
        .values(
            change_kind="returned",
            change_comment=sa.func.substr(rv.c.change_note, len(RETURNED) + 1),
        )
    )
    # Anything else was an editor's own note (or none): an edit, words kept verbatim.
    op.execute(
        rv.update()
        .where(rv.c.change_kind.is_(None))
        .values(change_kind="edited", change_comment=rv.c.change_note)
    )


def downgrade() -> None:
    # Rows written after the upgrade have no change_note: give them the old sentence back
    # before the columns go, so no history is lost.
    missing = rv.c.change_note.is_(None)
    for sentence, kind in SENTENCES.items():
        op.execute(
            rv.update().where(missing, rv.c.change_kind == kind).values(change_note=sentence)
        )
    op.execute(
        rv.update()
        .where(missing, rv.c.change_kind == "returned")
        .values(change_note=sa.literal(RETURNED) + sa.func.coalesce(rv.c.change_comment, ""))
    )
    op.execute(
        rv.update()
        .where(missing, rv.c.change_kind == "edited")
        .values(change_note=rv.c.change_comment)
    )
    op.drop_column("report_versions", "change_comment")
    op.drop_column("report_versions", "change_kind")
