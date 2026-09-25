"""Similar past Parliament questions (GET /pq/similar, guide 10.2).

Officers keep answers consistent by seeing how the same question was answered before: replies
approved here and the Ministry's uploaded PQ answers. It has to work without the model server
(keyword search only), stay inside the user's org unit, and never show a report to a role
that cannot open reports.
"""

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.core.db import get_db
from app.llm.client import LlmUnavailable
from app.main import app
from app.models.enums import House, QuestionType, ReportType
from app.services import similar_pq
from tests.conftest import fake_user

REPORT_ID = uuid.uuid4()
DOC_ID = uuid.uuid4()
CHUNK_A, CHUNK_B = uuid.uuid4(), uuid.uuid4()


def sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def model_down(*_args, **_kwargs):
    raise LlmUnavailable("model server not reachable")


def model_up(texts, timeout):
    return [[0.1] * 1024 for _ in texts]


# --- stubs -------------------------------------------------------------------------------------


def report_row():
    pq = SimpleNamespace(
        subject="Coal production in Jharkhand",
        question_text="(a) the coal production in Jharkhand in 2023-24; (b) the details thereof",
        house=House.LOK_SABHA,
        q_type=QuestionType.UNSTARRED,
        q_no="3749",
        answer_date=date(2024, 12, 11),
    )
    report = SimpleNamespace(
        id=REPORT_ID,
        title="Lok Sabha Unstarred Q. No. 3749",
        due_date=None,
        content_json={
            "header": {"subject": "Coal production in Jharkhand"},
            "blocks": [{"question": "the coal production", "text": "CCL produced 84 MT."}],
        },
    )
    return report, pq


def chunk_rows():
    doc = SimpleNamespace(id=DOC_ID, title="RS Q 12 answer")
    return [
        (SimpleNamespace(id=CHUNK_A, text="Coal production by CCL rose.", page_no=2), doc, None),
        (SimpleNamespace(id=CHUNK_B, text="Coal production again.", page_no=3), doc, None),
    ]


class Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    """Answers the similar-PQ queries from fixed rows and keeps the SQL it was asked to run."""

    def __init__(self) -> None:
        self.ran: list[str] = []

    def scalars(self, stmt):
        text = sql(stmt)
        self.ran.append(text)
        return [CHUNK_A, CHUNK_B] if "FROM chunks" in text else [REPORT_ID]

    def execute(self, stmt):
        text = sql(stmt)
        self.ran.append(text)
        return Rows(chunk_rows() if "FROM chunks" in text else [report_row()])


@pytest.fixture
def similar_as(client_as, monkeypatch):
    """similar_as(["analyst"]) -> (client, session), with the model server down."""
    monkeypatch.setattr(similar_pq, "embed_texts", model_down)

    def make(roles: list[str], org_code: str = "CMPDI"):
        client = client_as(roles, org_code)
        session = FakeSession()
        app.dependency_overrides[get_db] = lambda: session
        return client, session

    return make


def get(client, text: str, **params) -> list[dict]:
    res = client.get("/pq/similar", params={"text": text, **params})
    assert res.status_code == 200, res.text
    return res.json()


# --- endpoint ----------------------------------------------------------------------------------


def test_needs_login():
    assert TestClient(app).get("/pq/similar", params={"text": "coal"}).status_code == 401


@pytest.mark.parametrize("text", ["", "   ", "ab", " a  "])
def test_short_text_gives_an_empty_list_without_a_query(client_as, text):
    # client_as gives no database session: any query would fail.
    assert get(client_as(["viewer"]), text) == []


def test_works_without_the_model_server(similar_as):
    client, session = similar_as(["analyst"])
    items = get(client, "coal production in Jharkhand")
    assert {i["kind"] for i in items} == {"approved_reply", "pq_document"}
    assert not any("<=>" in q for q in session.ran), "no vector search without embeddings"
    assert any("to_tsquery" in q for q in session.ran)


def test_vector_search_is_used_when_the_model_answers(similar_as, monkeypatch):
    client, session = similar_as(["analyst"])
    monkeypatch.setattr(similar_pq, "embed_texts", model_up)
    assert get(client, "coal production")
    vector = [q for q in session.ran if "<=>" in q]
    assert any("chunks.embedding" in q for q in vector)
    assert any("parliament_questions.embedding" in q for q in vector)


def test_result_shape_and_links(similar_as):
    client, _ = similar_as(["analyst"])
    items = get(client, "coal production")
    reply = next(i for i in items if i["kind"] == "approved_reply")
    assert reply["report_id"] == str(REPORT_ID)
    assert reply["title"] == "Coal production in Jharkhand"
    assert (reply["house"], reply["q_type"], reply["q_no"]) == ("LS", "unstarred", "3749")
    assert reply["answer_date"] == "2024-12-11"
    assert reply["answer"] == "CCL produced 84 MT."
    assert "coal production in Jharkhand" in reply["snippet"]
    assert reply["document_id"] is None
    doc = next(i for i in items if i["kind"] == "pq_document")
    assert (doc["document_id"], doc["chunk_id"], doc["page"]) == (str(DOC_ID), str(CHUNK_A), 2)
    assert doc["title"] == doc["document_title"] == "RS Q 12 answer"
    assert doc["report_id"] is None


def test_one_result_per_document(similar_as):
    client, _ = similar_as(["analyst"])
    docs = [i["document_id"] for i in get(client, "coal production") if i["document_id"]]
    assert docs == [str(DOC_ID)]


def test_limit_is_applied(similar_as):
    client, _ = similar_as(["analyst"])
    assert len(get(client, "coal production", limit=1)) == 1


@pytest.mark.parametrize("role", ["operator", "reviewer"])
def test_roles_that_cannot_open_reports_see_documents_only(similar_as, role):
    client, session = similar_as([role])
    items = get(client, "coal production")
    assert items and {i["kind"] for i in items} == {"pq_document"}
    assert not any("FROM reports" in q for q in session.ran)


@pytest.mark.parametrize("role", ["admin", "analyst", "approver", "viewer"])
def test_roles_that_can_open_reports_see_approved_replies(similar_as, role):
    client, _ = similar_as([role])
    assert "approved_reply" in {i["kind"] for i in get(client, "coal production")}


def test_every_query_is_scoped_to_the_unit(similar_as, monkeypatch):
    client, session = similar_as(["analyst"], "NCL")
    monkeypatch.setattr(similar_pq, "embed_texts", model_up)
    get(client, "coal production")
    assert session.ran
    for q in session.ran:
        assert "reports.org_unit_id" in q or "documents.org_unit_id" in q, q


# --- queries -----------------------------------------------------------------------------------


def test_reply_query_takes_only_approved_or_exported_pq_replies_of_the_unit():
    text = sql(similar_pq.reply_keyword_stmt(fake_user(["analyst"], "NCL"), ["coal"]))
    assert "reports.report_type = " in text and "reports.status IN" in text
    assert "reports.org_unit_id = " in text
    assert "to_tsvector" in text and "jsonb_path_query_array" in text


def test_reply_query_can_leave_out_the_open_report():
    user = fake_user(["analyst"], "CIL_HQ")
    assert "reports.id != " in sql(similar_pq.reply_keyword_stmt(user, ["coal"], REPORT_ID))
    assert "reports.org_unit_id" not in sql(similar_pq.reply_keyword_stmt(user, ["coal"]))


def test_document_query_takes_only_pq_answers_the_user_may_see():
    text = sql(similar_pq.chunk_keyword_stmt(fake_user(["viewer"], "NCL"), ["coal"]))
    assert "documents.doc_type = " in text
    assert "documents.org_unit_id = " in text and "documents.is_public" in text
    assert "chunks.tsv @@" in text


# --- pure helpers ------------------------------------------------------------------------------


def test_report_question_reads_subject_and_parts():
    content = {
        "header": {"subject": "Coal import"},
        "blocks": [{"question": "the import in 2023-24"}, {"question": "the steps taken"}],
        "text": "full reply",
    }
    expected = "Coal import the import in 2023-24 the steps taken"
    assert similar_pq.report_question(content) == expected
    assert similar_pq.report_question({"text": "plain  reply"}) == "plain reply"
    assert similar_pq.report_question(None) == ""


def test_report_answer_skips_parts_not_found():
    content = {"blocks": [{"text": "84 MT.", "not_found": False}, {"text": "x", "not_found": True}]}
    assert similar_pq.report_answer(content) == "84 MT."


def test_excerpt_starts_near_the_first_match():
    text = " ".join(["filler"] * 100) + " coal production " + " ".join(["tail"] * 100)
    out = similar_pq.excerpt(text, ["coal"], width=80)
    assert "coal production" in out
    assert out.startswith("… ") and out.endswith(" …")
    assert len(out) <= 80 + 4


def test_excerpt_keeps_short_text_and_hindi():
    assert similar_pq.excerpt("कोयला  उत्पादन", ["कोयला"]) == "कोयला उत्पादन"


def test_fuse_rewards_items_found_by_both_methods():
    a, b, c = ("report", uuid.uuid4()), ("chunk", uuid.uuid4()), ("chunk", uuid.uuid4())
    assert similar_pq.fuse([[a, b], [c, b]])[0][0] == b


def test_remember_embeds_an_approved_pq_question(monkeypatch):
    pq = SimpleNamespace(id=uuid.uuid4(), subject="Coal", question_text="output", embedding=None)
    db = SimpleNamespace(get=lambda _model, _id: pq)
    monkeypatch.setattr(similar_pq, "embed_texts", model_up)
    similar_pq.remember(db, SimpleNamespace(report_type=ReportType.PQ_REPLY, pq_id=pq.id))
    assert pq.embedding == [0.1] * 1024


def test_remember_is_best_effort(monkeypatch):
    pq = SimpleNamespace(id=uuid.uuid4(), subject=None, question_text="output", embedding=None)
    db = SimpleNamespace(get=lambda _model, _id: pq)
    monkeypatch.setattr(similar_pq, "embed_texts", model_down)
    similar_pq.remember(db, SimpleNamespace(report_type=ReportType.PQ_REPLY, pq_id=pq.id))
    assert pq.embedding is None
    # Other report types have no question to remember.
    similar_pq.remember(None, SimpleNamespace(report_type=ReportType.MONTHLY, pq_id=None))


def test_one_shared_word_is_not_a_similar_question():
    # Nearly every question mentions coal: sharing only that word must not count.
    assert similar_pq.words_needed(["coal"]) == 1
    assert similar_pq.words_needed(["coal", "import"]) == 2
    assert similar_pq.words_needed(["w"] * 12) == 3
    assert similar_pq.shared_words(["coal", "import"], "Coal production rose") == 1
    assert similar_pq.shared_words(["coal", "produc"], "coal productions") == 2
    assert similar_pq.shared_words(["कोयला", "आयात"], "कोयला आयात घटा") == 2


def test_weak_keyword_matches_are_left_out(similar_as):
    client, _ = similar_as(["analyst"])
    # The stub rows share only "coal" with this question.
    assert get(client, "coal import steps") == []


def test_vector_matches_are_kept_without_shared_words(similar_as, monkeypatch):
    client, _ = similar_as(["analyst"])
    monkeypatch.setattr(similar_pq, "embed_texts", model_up)
    assert get(client, "fuel imports reduction")
