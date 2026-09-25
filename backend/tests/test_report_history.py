"""Version history is stored as a code plus a verbatim comment, not a sentence (#71).

A Hindi reader saw "v2 - Approved (द्वारा ...)" because "Approved" was an English
sentence in the database. The words now come from the frontend; the approver's own
comment is kept exactly as typed; rows written before the change still read correctly.
"""

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models import ReportVersion
from app.models.enums import ReportChangeKind, ReportStatus, ReportType
from app.services.report_history import describe

K = ReportChangeKind


# --- legacy rows: the sentences the API used to write -------------------------------------------


@pytest.mark.parametrize(
    ("note", "kind"),
    [
        ("Created", K.CREATED),
        ("Approved", K.APPROVED),
        ("First draft generated", K.DRAFTED),
        ("First draft generated from the question", K.DRAFTED_FROM_QUESTION),
    ],
)
def test_legacy_system_sentences_become_codes_with_no_comment(note, kind):
    assert describe(None, None, note) == (kind, None)


def test_legacy_returned_keeps_the_approvers_words_verbatim():
    words = "  Figure for NCL is wrong — कृपया दोबारा जाँचें.\nSee p. 4  "
    assert describe(None, None, f"Returned: {words}") == (K.RETURNED, words)


def test_legacy_editor_note_is_kept_as_an_edit_comment():
    assert describe(None, None, "Fixed the table totals") == (K.EDITED, "Fixed the table totals")


def test_legacy_row_with_no_note_is_a_plain_edit():
    assert describe(None, None, None) == (K.EDITED, None)


# --- new rows ----------------------------------------------------------------------------------


def test_a_stored_code_wins_and_its_comment_is_untouched():
    assert describe("returned", "Recheck p. 4", None) == (K.RETURNED, "Recheck p. 4")
    assert describe("approved", None, None) == (K.APPROVED, None)


def test_an_unknown_code_falls_back_to_the_words_rather_than_failing():
    assert describe("merged", None, "Created") == (K.CREATED, None)
    assert describe("merged", None, None) == (K.EDITED, None)


# --- endpoints ---------------------------------------------------------------------------------


class FakeDb:
    """`scalar` answers the scoped report lookup, then the latest version number."""

    def __init__(self, report, versions=()):
        self.report = report
        self.versions = list(versions)
        self.added = []
        self._scalar_calls = 0

    def scalar(self, stmt):
        self._scalar_calls += 1
        return self.report if self._scalar_calls == 1 else len(self.versions)

    def scalars(self, stmt):
        return iter(self.versions)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    def commit(self):
        self.flush()

    def refresh(self, obj):
        obj.created_at = obj.updated_at = obj.created_at or datetime(2026, 9, 26)


def a_report(status=ReportStatus.IN_REVIEW):
    now = datetime(2026, 9, 26)
    return SimpleNamespace(
        id=uuid.uuid4(),
        report_type=ReportType.PQ_REPLY,
        title="PQ 123",
        status=status,
        content_json={"text": "Reply"},
        org_unit_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        approver_id=None,
        due_date=None,
        created_at=now,
        updated_at=now,
    )


def a_version(n, *, note=None, kind=None, comment=None):
    return SimpleNamespace(
        version=n,
        content_json={"text": "Reply"},
        editor=SimpleNamespace(id=uuid.uuid4(), name="Demo Approver", email="a@koylasetu.local"),
        change_note=note,
        change_kind=kind,
        change_comment=comment,
        created_at=datetime(2026, 9, 26),
    )


@pytest.fixture
def as_role(client_as):
    from app.core.db import get_db
    from app.main import app

    def make(roles, db):
        http = client_as(roles)
        app.dependency_overrides[get_db] = lambda: db
        return http

    return make


def test_versions_endpoint_returns_codes_for_old_and_new_rows(as_role):
    report = a_report(ReportStatus.RETURNED)
    db = FakeDb(
        report,
        [
            a_version(4, kind="returned", comment="सही आँकड़ा डालें"),
            a_version(3, note="Returned: Check NCL "),
            a_version(2, note="Approved"),
            a_version(1, note="Created"),
        ],
    )
    rows = as_role(["viewer"], db).get(f"/reports/{report.id}/versions").json()
    assert [(r["version"], r["change_kind"], r["change_comment"]) for r in rows] == [
        (4, "returned", "सही आँकड़ा डालें"),
        (3, "returned", "Check NCL "),
        (2, "approved", None),
        (1, "created", None),
    ]
    assert rows[2]["change_note"] == "Approved"  # the recorded sentence is still there


def test_reject_stores_a_code_and_the_comment_exactly_as_typed(as_role):
    report = a_report(ReportStatus.IN_REVIEW)
    db = FakeDb(report, [a_version(1, kind="created")])
    words = "Figure on p. 4 doesn't match — कृपया जाँचें"
    res = as_role(["approver"], db).post(f"/reports/{report.id}/reject", json={"comment": words})
    assert res.status_code == 200, res.text
    (version,) = [o for o in db.added if isinstance(o, ReportVersion)]
    assert version.change_kind == "returned" and version.change_comment == words
    assert version.change_note is None and version.version == 2


def test_approve_and_edit_store_codes_not_sentences(as_role):
    report = a_report(ReportStatus.IN_REVIEW)
    db = FakeDb(report, [a_version(1, kind="created")])
    assert as_role(["approver"], db).post(f"/reports/{report.id}/approve").status_code == 200
    (approved,) = [o for o in db.added if isinstance(o, ReportVersion)]
    assert (approved.change_kind, approved.change_comment, approved.change_note) == (
        "approved",
        None,
        None,
    )

    report = a_report(ReportStatus.DRAFT)
    db = FakeDb(report, [a_version(1, kind="created")])
    body = {"content_json": {"text": "New"}, "change_note": "Tightened the reply"}
    assert as_role(["analyst"], db).patch(f"/reports/{report.id}", json=body).status_code == 200
    (edited,) = [o for o in db.added if isinstance(o, ReportVersion)]
    assert (edited.change_kind, edited.change_comment) == ("edited", "Tightened the reply")


def test_create_stores_the_created_code(as_role):
    db = FakeDb(None)
    body = {"report_type": "pq_reply", "title": "PQ 9"}
    res = as_role(["analyst"], db).post("/reports", json=body)
    assert res.status_code == 201, res.text
    (version,) = [o for o in db.added if isinstance(o, ReportVersion)]
    assert version.change_kind == "created" and version.change_note is None
