"""The audit log must scope to the caller's org unit like every other list.

Before this, a subsidiary Admin or Approver could read every other unit's uploaded
filenames, report titles and user emails out of the audit log's details_json.
"""

from sqlalchemy import select

from app.core.deps import scope_to_user
from app.models import AuditLog
from app.services import audit
from tests.conftest import fake_user


class CapturingSession:
    """Stands in for a Session; keeps whatever was add()ed so we can inspect it."""

    def __init__(self) -> None:
        self.added: list[AuditLog] = []

    def add(self, row: AuditLog) -> None:
        self.added.append(row)


def where(user) -> str | None:
    """The WHERE clause the audit list would run for this user, as SQL text."""
    clause = scope_to_user(select(AuditLog), AuditLog, user).whereclause
    return None if clause is None else str(clause)


def test_subsidiary_user_query_is_filtered_by_unit():
    assert where(fake_user(["admin"], "NCL")) == "audit_log.org_unit_id = :org_unit_id_1"


def test_hq_and_ministry_still_see_every_unit():
    assert where(fake_user(["admin"], "CIL_HQ")) is None
    assert where(fake_user(["approver"], "MINISTRY")) is None


def test_record_stamps_the_actors_unit():
    db, user = CapturingSession(), fake_user(["operator"], "NCL")
    audit.record(db, "upload", actor=user, entity="document")
    (row,) = db.added
    assert row.org_unit_id == user.org_unit_id
    assert row.user_id == user.id


def test_a_failed_login_on_a_known_email_reaches_that_users_unit():
    """No actor to attribute, but their unit should still see the attempt."""
    db, user = CapturingSession(), fake_user(["analyst"], "MCL")
    audit.record(db, "login_failed", actor=None, org_unit_id=user.org_unit_id)
    (row,) = db.added
    assert row.user_id is None
    assert row.org_unit_id == user.org_unit_id


def test_an_action_with_no_unit_stays_null_and_so_stays_hq_only():
    db = CapturingSession()
    audit.record(db, "login_failed", actor=None, details={"email": "nobody@example.com"})
    (row,) = db.added
    assert row.org_unit_id is None
