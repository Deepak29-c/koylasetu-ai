"""POST /documents `title` field (issue #15): what actually gets stored, with a stub session
that captures the Document the endpoint builds (no database)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.api import documents as documents_api
from app.core.db import get_db
from app.main import app
from app.models import Document
from app.services import storage

PDF = b"%PDF-1.7\n%test\n"


class StubSession:
    """Just enough of a SQLAlchemy session for the upload path: no existing documents."""

    def __init__(self) -> None:
        self.added: list = []

    def scalar(self, _stmt):
        return None  # no duplicate by sha256

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        for obj in self.added:
            if isinstance(obj, Document) and obj.id is None:
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(UTC)
                obj.pages_done = 0

    def commit(self) -> None:
        pass

    def documents(self) -> list[Document]:
        return [o for o in self.added if isinstance(o, Document)]


@pytest.fixture
def upload(client_as, tmp_path, monkeypatch):
    """upload(title=..., filename=...) -> (response, the Document that would be inserted)."""
    monkeypatch.setattr(storage, "storage_root", lambda: tmp_path)
    monkeypatch.setattr(documents_api, "enqueue_ingest", lambda _id: False)

    def make(title: str | None, filename: str = "1638334697_606_0001.pdf"):
        client = client_as(["admin"], "CIL_HQ")
        session = StubSession()
        app.dependency_overrides[get_db] = lambda: session
        data = {"doc_type": "pq_answer", "is_public": "true"}
        if title is not None:
            data["title"] = title
        res = client.post("/documents", data=data, files={"files": (filename, PDF)})
        return res, session.documents()

    return make


def test_single_file_title_is_stored(upload):
    res, docs = upload("  Coal   Shortage ")
    assert res.status_code == 200, res.text
    assert res.json()[0]["result"] == "created"
    assert [d.title for d in docs] == ["Coal Shortage"]  # whitespace tidied
    assert docs[0].original_filename == "1638334697_606_0001.pdf"
    assert res.json()[0]["document"]["title"] == "Coal Shortage"


def test_500_character_title_is_accepted(upload):
    res, docs = upload("x" * 500)
    assert res.status_code == 200, res.text
    assert docs[0].title == "x" * 500


@pytest.mark.parametrize("title", [None, "", "   "])
def test_missing_or_blank_title_falls_back_to_the_file_name(upload, title):
    res, docs = upload(title)
    assert res.status_code == 200, res.text
    assert docs[0].title == "1638334697_606_0001"
