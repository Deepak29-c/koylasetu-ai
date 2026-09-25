"""New PQ reply form: parts preview, question text from a file, and the reply's due date.
No database and no model: the endpoints that save use the stub session of test_pq_reply."""

import io

import docx
import pymupdf
import pytest

from app.llm import client
from app.models import Report
from app.services import pq_reply, qa, question_file, storage
from tests.test_pq_reply import PQ_BODY, PQ_EN, PQ_HI, FakeSession, fake_ask

# --- POST /pq-replies/parts ---------------------------------------------------------------------


def test_parts_preview_uses_the_marker_splitter(client_as, monkeypatch):
    def no_model(*_a, **_k):
        raise AssertionError("the preview must not call the model")

    monkeypatch.setattr(client, "chat", no_model)
    res = client_as(["analyst"]).post("/pq-replies/parts", json={"question_text": PQ_EN})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["method"] == "markers"
    assert body["intro"] == "Will the Minister of COAL be pleased to state:"
    _, expected = pq_reply.split_by_markers(PQ_EN)
    assert body["parts"] == [{"part": p.label, "text": p.text} for p in expected]
    assert body["max_parts"] == pq_reply.MAX_PARTS


def test_parts_preview_of_a_hindi_question(client_as):
    res = client_as(["analyst"]).post("/pq-replies/parts", json={"question_text": PQ_HI})
    assert [p["part"] for p in res.json()["parts"]] == ["क", "ख", "ग"]


@pytest.mark.parametrize("text", ["", "What is the coal production of NCL in 2024-25?"])
def test_parts_preview_without_markers_is_single(client_as, text):
    res = client_as(["analyst"]).post("/pq-replies/parts", json={"question_text": text})
    assert res.status_code == 200, res.text
    assert res.json() | {"max_parts": 0} == {
        "method": "single",
        "intro": "",
        "parts": [],
        "max_parts": 0,
    }


def test_parts_preview_needs_edit_reports(client_as):
    res = client_as(["viewer"]).post("/pq-replies/parts", json={"question_text": PQ_EN})
    assert res.status_code == 403


def test_parts_preview_rejects_text_longer_than_the_form_takes(client_as):
    res = client_as(["analyst"]).post("/pq-replies/parts", json={"question_text": "x" * 20001})
    assert res.status_code == 422


# --- POST /pq-replies/question-text -------------------------------------------------------------


def pdf_bytes(text: str | None) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def docx_bytes(*paragraphs: str) -> bytes:
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


@pytest.fixture
def post_file(client_as, tmp_path, monkeypatch):
    """post_file(name, data, roles) -> response; checks the temporary file is deleted."""
    monkeypatch.setattr(storage, "storage_root", lambda: tmp_path)

    def post(name: str, data: bytes, roles=("analyst",)):
        res = client_as(list(roles)).post("/pq-replies/question-text", files={"file": (name, data)})
        assert not any((tmp_path / "tmp").glob("*"))  # the file is not kept
        return res

    return post


def test_question_text_from_a_pdf(post_file):
    res = post_file("pq.pdf", pdf_bytes("(a) the coal production of NCL; (b) the target?"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["filename"] == "pq.pdf" and body["truncated"] is False
    assert "(a) the coal production of NCL; (b) the target?" in body["text"]


def test_question_text_from_word(post_file):
    data = docx_bytes("Will the Minister of COAL be pleased to state:", "", "", "(a) whether …")
    res = post_file("question.docx", data)
    assert res.status_code == 200, res.text
    assert res.json()["text"] == "Will the Minister of COAL be pleased to state:\n\n(a) whether …"


def test_question_text_from_a_text_file(post_file):
    res = post_file("q.txt", "﻿(क) कोयला उत्पादन;\r\n(ख) लक्ष्य?  \r\n".encode())
    assert res.status_code == 200, res.text
    assert res.json()["text"] == "(क) कोयला उत्पादन;\n(ख) लक्ष्य?"


def test_long_text_is_cut_to_what_the_question_box_takes(post_file):
    res = post_file("long.txt", ("word " * 5000).encode())
    body = res.json()
    assert body["truncated"] is True and len(body["text"]) <= question_file.MAX_CHARS


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("sheet.csv", b"a,b\n1,2\n", "pq_file_type"),  # an upload type, but not a question
        ("photo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "pq_file_type"),
        ("notes.txt", b"\x00\x01binary", "pq_file_type"),
        ("fake.pdf", b"just text", "pq_file_type"),  # the type comes from the content
        ("latin.txt", "caf\xe9".encode("latin-1"), "pq_file_unreadable"),
        ("broken.pdf", b"%PDF-1.7\n garbage", "pq_file_unreadable"),
        ("scan.pdf", pdf_bytes(None), "pq_file_no_text"),
    ],
)
def test_question_file_errors_carry_a_code(post_file, name, data, code):
    res = post_file(name, data)
    assert res.status_code == 422, res.text
    assert res.json()["code"] == code


def test_question_file_over_the_upload_limit(post_file, monkeypatch):
    from app.core import config

    settings = config.get_settings().model_copy(update={"max_upload_mb": 0})
    monkeypatch.setattr("app.api.pq_replies.get_settings", lambda: settings)
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    res = post_file("q.txt", b"(a) the production?")
    assert res.status_code == 413
    assert res.json()["code"] == "pq_file_too_large"


def test_question_file_needs_edit_reports(post_file):
    assert post_file("q.txt", b"(a) x", roles=("viewer",)).status_code == 403


# --- due date on the draft ----------------------------------------------------------------------


@pytest.fixture
def analyst(client_as, monkeypatch):
    from app.core.db import get_db
    from app.main import app

    monkeypatch.setattr(client, "ensure_available", lambda: None)
    monkeypatch.setattr(qa, "ask", fake_ask)
    session = FakeSession()
    http = client_as(["analyst"])
    app.dependency_overrides[get_db] = lambda: session
    return http, session


def saved_report(session: FakeSession) -> Report:
    return next(o for o in session.added if isinstance(o, Report))


def test_draft_due_date_is_set_on_the_report(analyst):
    http, session = analyst
    res = http.post("/pq-replies/draft", json=PQ_BODY | {"due_date": "2025-02-10"})
    assert res.status_code == 201, res.text
    assert res.json()["report"]["due_date"] == "2025-02-10"
    assert str(saved_report(session).due_date) == "2025-02-10"


def test_draft_without_due_date_falls_back_to_the_answer_date(analyst):
    http, session = analyst
    res = http.post("/pq-replies/draft", json=PQ_BODY)
    assert res.status_code == 201, res.text
    assert res.json()["report"]["due_date"] == PQ_BODY["answer_date"]


def test_draft_with_neither_date_has_no_due_date(analyst):
    http, _ = analyst
    res = http.post("/pq-replies/draft", json=PQ_BODY | {"answer_date": None})
    assert res.status_code == 201, res.text
    assert res.json()["report"]["due_date"] is None
