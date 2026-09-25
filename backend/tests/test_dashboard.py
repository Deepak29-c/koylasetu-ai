"""Home dashboard: each role is told about the work it can actually act on."""

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app

COUNT = 3


class StubSession:
    """Every count query returns the same number; we assert on which panels appear."""

    def scalar(self, _stmt) -> int:
        return COUNT


@pytest.fixture
def dashboard_as(client_as):
    def make(roles: list[str], org_code: str = "CMPDI") -> dict:
        client = client_as(roles, org_code)
        app.dependency_overrides[get_db] = StubSession
        res = client.get("/dashboard/summary")
        assert res.status_code == 200, res.text
        return res.json()

    return make


def test_needs_login():
    assert TestClient(app).get("/dashboard/summary").status_code == 401


def test_reviewer_sees_review_and_documents_but_not_reports(dashboard_as):
    body = dashboard_as(["reviewer"])
    assert body["review"]["pending_facts"] == COUNT
    assert body["documents"]["processing"] == COUNT
    assert body["reports"] is None


def test_analyst_sees_reports_and_documents_but_not_review(dashboard_as):
    body = dashboard_as(["analyst"])
    assert body["reports"]["my_drafts"] == COUNT
    assert body["documents"]["processing"] == COUNT
    assert body["review"] is None


def test_only_an_approver_is_told_about_reports_awaiting_approval(dashboard_as):
    assert dashboard_as(["analyst"])["reports"]["awaiting_approval"] == 0
    assert dashboard_as(["approver"])["reports"]["awaiting_approval"] == COUNT


def test_viewer_sees_reports_and_activity_only(dashboard_as):
    body = dashboard_as(["viewer"])
    assert body["reports"] is not None  # a Viewer may export reports, so may see them
    assert body["activity"]["questions_this_month"] == COUNT
    assert body["documents"] is None
    assert body["review"] is None


def test_operator_gets_no_reports_panel(dashboard_as):
    body = dashboard_as(["operator"])
    assert body["reports"] is None
    assert body["documents"] is not None
