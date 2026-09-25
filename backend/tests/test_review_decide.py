"""A reviewer's decision end to end (fake session): fact status, review log and audit row."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import review
from app.models import AuditLog, ReviewActionLog
from app.models.enums import DocumentStatus, FactStatus, ReviewAction
from app.schemas.review import ReviewDecision


class FakeDb:
    def __init__(self, earlier=None):
        self.added = []
        self.committed = False
        # db.scalar is asked twice: the fact's earlier decision, then "open issues left?"
        self._scalars = [earlier, False]

    def scalars(self, _stmt):
        return []  # no open validation issues left on the fact

    def scalar(self, _stmt):
        return self._scalars.pop(0)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        pass

    def commit(self):
        self.committed = True


@pytest.fixture
def setup(monkeypatch):
    fact = SimpleNamespace(
        id=uuid.uuid4(), value=12.7, value_std=12.7, status=FactStatus.FLAGGED, label="NCL · Dec"
    )
    doc = SimpleNamespace(id=uuid.uuid4(), status=DocumentStatus.NEEDS_REVIEW)
    monkeypatch.setattr(review, "_scoped_fact", lambda *_: (fact, doc))
    user = SimpleNamespace(id=uuid.uuid4(), org_unit_id=uuid.uuid4())
    return fact, doc, user


def test_accept_verifies_and_writes_review_and_audit_rows(setup):
    fact, doc, user = setup
    db = FakeDb()
    review.decide(fact.id, ReviewDecision(action="ACCEPT"), None, user, db)
    assert fact.status == FactStatus.VERIFIED and doc.status == DocumentStatus.PROCESSED
    (log,) = [r for r in db.added if isinstance(r, ReviewActionLog)]
    (audit,) = [r for r in db.added if isinstance(r, AuditLog)]
    assert log.user_id == user.id
    assert (audit.action, audit.user_id, audit.org_unit_id) == (
        "review_accept",
        user.id,
        user.org_unit_id,
    )
    assert db.committed


def test_edit_scales_the_standard_value(setup):
    fact, _, user = setup
    fact.value, fact.value_std = 1270.0, 127.0  # lakh tonnes -> MT
    decision = ReviewDecision(action="EDIT", new_value="1280", comment="typo")
    review.decide(fact.id, decision, None, user, FakeDb())
    assert (fact.value, fact.value_std, fact.status) == (1280.0, 128.0, FactStatus.VERIFIED)


def test_changing_an_earlier_decision_needs_a_comment(setup):
    fact, _, user = setup
    with pytest.raises(HTTPException) as err:
        review.decide(
            fact.id, ReviewDecision(action="ACCEPT"), None, user, FakeDb(ReviewAction.REJECT)
        )
    assert err.value.status_code == 422


def test_changed_decision_is_recorded_with_what_it_replaced(setup):
    fact, _, user = setup
    fact.status = FactStatus.VERIFIED  # accepted earlier by mistake
    db = FakeDb(ReviewAction.ACCEPT)
    decision = ReviewDecision(action="REJECT", comment="wrong column: this is the total")
    review.decide(fact.id, decision, None, user, db)
    (audit,) = [r for r in db.added if isinstance(r, AuditLog)]
    assert fact.status == FactStatus.REJECTED
    assert audit.details_json["changed_from"] == "ACCEPT"


def test_only_reviewers_see_earlier_decisions(client_as):
    assert client_as(["analyst"]).get("/review/decided").status_code == 403
    assert client_as(["viewer"]).get("/review/decided").status_code == 403
