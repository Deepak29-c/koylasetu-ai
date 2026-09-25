"""Read a report version's history line as a code plus a verbatim comment (#71).

Version history is the audit trail of a reply, so a Hindi reader must see it in Hindi.
New rows store `change_kind` (a code) and `change_comment` (human words, never
translated). Rows written before that stored an English sentence in `change_note`;
`describe` maps those sentences to the same code + comment so they render the same way,
and anything it does not recognise is kept word for word as a comment.
"""

from app.models.enums import ReportChangeKind

RETURNED_PREFIX = "Returned: "

# The exact sentences the API used to write, before #71.
_LEGACY_SENTENCES: dict[str, ReportChangeKind] = {
    "Created": ReportChangeKind.CREATED,
    "Approved": ReportChangeKind.APPROVED,
    "First draft generated": ReportChangeKind.DRAFTED,
    "First draft generated from the question": ReportChangeKind.DRAFTED_FROM_QUESTION,
}


def describe(
    change_kind: str | None, change_comment: str | None, change_note: str | None
) -> tuple[ReportChangeKind, str | None]:
    """(kind, comment) for one version row, whether it was written before #71 or after."""
    if change_kind:
        try:
            return ReportChangeKind(change_kind), change_comment
        except ValueError:
            pass  # a code this build doesn't know: fall through and keep the words
    if change_note is None:
        return ReportChangeKind.EDITED, change_comment
    if change_note in _LEGACY_SENTENCES:
        return _LEGACY_SENTENCES[change_note], None
    if change_note.startswith(RETURNED_PREFIX):
        return ReportChangeKind.RETURNED, change_note[len(RETURNED_PREFIX) :]
    # Anything else was an editor's own note from PATCH /reports/{id}: keep it verbatim.
    return ReportChangeKind.EDITED, change_note
