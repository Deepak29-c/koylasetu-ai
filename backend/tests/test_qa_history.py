"""Reopening a past answer (#40).

Opening a citation used to lose the answer, the question and every other citation, so
checking a second figure meant asking again and waiting 30-55 s. qa_logs already held
everything; there was simply no way to read it back.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app


class EmptySession:
    def scalars(self, _stmt):
        return []

    def get(self, _model, _id):
        return None


@pytest.fixture
def qa_client(client_as):
    def make(roles: list[str]) -> TestClient:
        client = client_as(roles)
        app.dependency_overrides[get_db] = EmptySession
        return client

    return make


def test_history_needs_login():
    assert TestClient(app).get("/qa/history").status_code == 401


def test_history_is_not_read_as_an_answer_id(qa_client):
    """/qa/history must be declared before /qa/{qa_id}, or it 422s as a bad UUID."""
    res = qa_client(["viewer"]).get("/qa/history")
    assert res.status_code == 200, res.text
    assert res.json() == []


def test_everyone_who_may_ask_may_see_their_own_history(qa_client):
    for role in ("admin", "operator", "reviewer", "analyst", "approver", "viewer"):
        assert qa_client([role]).get("/qa/history").status_code == 200


def test_reopening_an_answer_that_is_not_yours_is_not_found(qa_client):
    missing = "00000000-0000-0000-0000-000000000001"
    assert qa_client(["analyst"]).get(f"/qa/{missing}").status_code == 404


def test_reopening_needs_login():
    missing = "00000000-0000-0000-0000-000000000001"
    assert TestClient(app).get(f"/qa/{missing}").status_code == 401
