"""Topic explorer (guide section 11): cleaning, word cloud, periods, topics, PQ parsing, API."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.api import topics as topics_api
from app.models.enums import House, QuestionType
from app.services.pq_parse import parse_answer_date, parse_pq, split_parts
from app.services.topics import (
    TopicDoc,
    build_topics,
    fy_start_year,
    keep_question,
    mentions_subsidiary,
    period_counts,
    session_of,
    singular,
    tokenize,
    word_cloud,
)
from worker.topics import ordered_text, should_rebuild

# --- Cleaning ------------------------------------------------------------------------------


def test_tokenize_english_drops_numbers_punctuation_and_stopwords():
    text = (
        "(a) whether the Government has taken steps to increase Coking Coal production "
        "in 2023-24, State-wise; and (b) the details thereof?"
    )
    assert tokenize(text) == ["increase", "coking", "production"]


def test_tokenize_merges_plurals_and_keeps_hyphenated_terms():
    assert tokenize("washeries plants e-auction mines process status") == [
        "washery",
        "plant",
        "e-auction",
        "mine",
        "process",
        "status",
    ]
    assert singular("industries") == "industry"
    assert singular("gas") == "gas"


def test_tokenize_hindi_drops_hindi_and_domain_stopwords_and_digits():
    text = "क्या सरकार ने वर्ष २०२३ में कोकिंग कोयले के उत्पादन में वृद्धि की है; तत्संबंधी ब्यौरा क्या है?"
    assert tokenize(text) == ["कोकिंग", "उत्पादन", "वृद्धि"]


def test_hindi_glossary_is_used_only_when_asked():
    assert tokenize("कोकिंग कोयले की वाशरी") == ["कोकिंग", "वाशरी"]
    assert tokenize("कोकिंग कोयले की वाशरी", glossary=True) == ["coking", "washery"]


def test_word_cloud_counts_each_word_once_per_text():
    cloud = word_cloud(["mine safety safety safety", "mine accident", "coking washery"])
    assert cloud[0] == {"text": "mine", "weight": 2}
    assert {"text": "safety", "weight": 1} in cloud
    assert len(word_cloud(["a b c mine"] * 3, top_n=1)) == 1


# --- Periods and filters -------------------------------------------------------------------


def test_session_of_and_period_counts():
    assert session_of(date(2021, 2, 10)) == "budget"
    assert session_of(date(2022, 7, 27)) == "monsoon"
    assert session_of(date(2019, 12, 11)) == "winter"
    counts = period_counts([date(2021, 2, 10), date(2021, 3, 24), date(2022, 7, 27), None])
    assert counts == {
        "year": {"2021": 2, "2022": 1},
        "session": {"2021-budget": 2, "2022-monsoon": 1},
        "undated": 1,
    }


def test_word_cloud_filters():
    assert keep_question(date(2021, 7, 28), "x", "monsoon", None)
    assert not keep_question(date(2021, 2, 1), "x", "monsoon", None)
    assert not keep_question(None, "x", "winter", None)
    assert mentions_subsidiary("Supply by South Eastern Coalfields Limited", "SECL")
    assert not mentions_subsidiary("Supply by South Eastern Coalfields Limited", "ECL")
    assert mentions_subsidiary("output of ECL mines", "ecl")
    assert fy_start_year("FY 2023-24") == 2023
    assert fy_start_year(None) is None


# --- Topics --------------------------------------------------------------------------------

CORPUS = [
    ("c1", "Coking coal washeries: capacity of coking coal washeries of BCCL", date(2021, 2, 3)),
    ("c2", "Production of coking coal and new washeries planned", date(2022, 7, 20)),
    ("c3", "Import of coking coal for steel plants and washeries", date(2022, 3, 30)),
    ("c4", "Coking coal washery performance and coking coal yield", date(2023, 2, 8)),
    ("s1", "Accidents in coal mines and safety audit of mines", date(2019, 12, 11)),
    ("s2", "Mine safety: fatal accidents in underground mines", date(2021, 3, 24)),
    ("s3", "Safety of mine workers and accidents reported", date(2022, 7, 27)),
    ("s4", "Mine accidents, deaths and safety measures in mines", date(2023, 7, 26)),
    ("a1", "Spot e-auction of coal: prices and premium in e-auction", date(2019, 11, 27)),
    ("a2", "E-auction premium over notified prices", date(2021, 8, 4)),
    ("a3", "Coal e-auction volumes and auction prices", date(2022, 3, 23)),
    ("a4", "Special forward e-auction prices for power", date(2023, 12, 6)),
]


def _docs():
    return [TopicDoc(i, text, day) for i, text, day in CORPUS]


def test_build_topics_groups_a_fixed_corpus_by_subject():
    drafts = build_topics(_docs(), n_topics=3)
    groups = sorted(sorted(m.id for m in d.members) for d in drafts)
    assert groups == [["a1", "a2", "a3", "a4"], ["c1", "c2", "c3", "c4"], ["s1", "s2", "s3", "s4"]]
    by_first = {d.members[0].id[0]: d for d in drafts}
    assert "coking" in " ".join(by_first["c"].keywords)
    assert "e-auction" in " ".join(by_first["a"].keywords)
    assert "accident" in " ".join(by_first["s"].keywords)
    assert [d.topic_no for d in drafts] == [0, 1, 2]
    assert all(d.size == 4 and d.label for d in drafts)
    assert by_first["s"].period_counts["year"] == {"2019": 1, "2021": 1, "2022": 1, "2023": 1}
    assert all(m.keywords for d in drafts for m in d.members)


def test_build_topics_is_deterministic():
    first = build_topics(_docs(), n_topics=3)
    second = build_topics(list(reversed(_docs())), n_topics=3)
    assert [(d.label, d.size) for d in first] == [(d.label, d.size) for d in second]


def test_hindi_question_joins_the_matching_english_topic():
    docs = _docs() + [TopicDoc("h1", "कोकिंग कोयले की वाशरी और कोकिंग कोयले का उत्पादन", None)]
    drafts = build_topics(docs, n_topics=3)
    coking = next(d for d in drafts if any(m.id == "c1" for m in d.members))
    assert "h1" in {m.id for m in coking.members}
    assert coking.period_counts["undated"] == 1


def test_build_topics_needs_at_least_two_usable_questions():
    assert build_topics([]) == []
    assert build_topics([TopicDoc("x", "the details thereof", None)] * 3) == []


def test_should_rebuild_rule():
    assert should_rebuild(1, has_run=False, min_new=5)
    assert not should_rebuild(0, has_run=False, min_new=5)
    assert not should_rebuild(4, has_run=True, min_new=5)
    assert should_rebuild(5, has_run=True, min_new=5)
    assert should_rebuild(0, has_run=True, min_new=5, force=True)


def test_ordered_text_sorts_by_page_then_position():
    chunks = [
        SimpleNamespace(page_no=2, bbox=[0, 10, 1, 1], text="page two"),
        SimpleNamespace(page_no=1, bbox=[0, 300, 1, 1], text="lower"),
        SimpleNamespace(page_no=1, bbox=[0, 20, 1, 1], text="upper"),
        SimpleNamespace(page_no=1, bbox=None, text="no box"),
    ]
    assert ordered_text(chunks) == "upper\nlower\nno box\npage two"


# --- PQ parsing (real header text from Ministry of Coal PQ answers) ------------------------

CLEAN_PQ = """GOVERNMENT OF INDIA
MINISTRY OF COAL
LOK SABHA
UNSTARRED QUESTION NO. 3749
TO BE ANSWERED ON 11.12.2019
Rely on Coal for Power Generation
3749. SHRI GAURAV GOGOI:
Will the Minister of COAL be pleased to state:
(a) whether there is rise in the use of coal over the past five years and if so,
the details thereof;
(b) the extent to which India relies on coal for its power and total electricity
generation; and
(c) whether India's continuous use of coal is likely to hamper the country's
fight against climate change?
ANSWER
MINISTER OF PARLIAMENTARY AFFAIRS, COAL AND MINES
(SHRI PRALHAD JOSHI)
(a) & (b): Central Electricity Authority (CEA) has informed ...
"""

# OCR text layer of an older scan (1627449894_1428.pdf), shortened.
OCR_PQ = """GOVERNMENT OF INDIA
MIMSTRY OF COAL
LOK SABIIA
ITNSTARRED QTTESTTOI{ NO. 1428
TO BEANSUTERED ON 24.O7.2O2L
Coal Production and Import
1428. STIRI SITML BABI'RAO MEIIDHE:
SIIRIMATI QIIEEN OJA:
UIiII the Mlnister of Coal be pleased to Btates
(a) the details of production and consumption of coal in the country;
(b) whether a major portion of coal consumption of the country is imported;
/u{swtR
MINISTER OF PARLIAMENTARY AFFAIRS' COAL /TND MINF,S
(SHRI PRALHAD JOSHII
"""

HINDI_PQ = """भारत सरकार
कोयला मंत्रालय
लोक सभा
अतारांकित प्रश्न संख्या 1234
उत्तर देने की तारीख 10.02.2021
कोकिंग कोयले का आयात
1234. श्री राम कुमार:
क्या कोयला मंत्री यह बताने की कृपा करेंगे कि:
(क) क्या सरकार का कोकिंग कोयले का आयात कम करने का प्रस्ताव है;
उत्तर
कोयला और खान मंत्री
"""


def test_parse_clean_pq():
    pq = parse_pq(CLEAN_PQ)
    assert pq is not None
    assert (pq.house, pq.q_type, pq.q_no) == (House.LOK_SABHA, QuestionType.UNSTARRED, "3749")
    assert pq.answer_date == date(2019, 12, 11)
    assert pq.subject == "Rely on Coal for Power Generation"
    assert pq.mp_names == ["SHRI GAURAV GOGOI"]
    assert pq.question_text.startswith("(a) whether there is rise in the use of coal")
    assert pq.question_text.endswith("fight against climate change?")
    assert [p["label"] for p in pq.parts] == ["a", "b", "c"]
    assert pq.answer_text.startswith("MINISTER OF PARLIAMENTARY AFFAIRS")


def test_parse_ocr_pq_tolerates_ocr_slips():
    pq = parse_pq(OCR_PQ)
    assert pq is not None
    assert (pq.house, pq.q_type, pq.q_no) == (House.LOK_SABHA, QuestionType.UNSTARRED, "1428")
    assert pq.answer_date == date(2021, 7, 24)
    assert pq.subject == "Coal Production and Import"
    assert len(pq.mp_names) == 2
    assert pq.question_text.startswith("(a) the details of production")
    assert pq.question_text.endswith("is imported;")


def test_parse_hindi_pq():
    pq = parse_pq(HINDI_PQ)
    assert pq is not None
    assert (pq.house, pq.q_type, pq.q_no) == (House.LOK_SABHA, QuestionType.UNSTARRED, "1234")
    assert pq.answer_date == date(2021, 2, 10)
    assert pq.subject == "कोकिंग कोयले का आयात"
    assert "आयात कम करने" in pq.question_text


def test_parse_rejects_non_pq_text_and_bad_dates():
    assert parse_pq("Annual Report 2023-24\nChapter 1\nCoal production rose.") is None
    assert parse_answer_date("TO BE ANSWERED ON 2().07.2022") == date(2022, 7, 20)
    assert parse_answer_date("TO BE ANSWERED ON 45.13.2022") is None
    assert split_parts("(a) one; (b) two") == [
        {"label": "a", "text": "one"},
        {"label": "b", "text": "two"},
    ]


# --- API -----------------------------------------------------------------------------------


@pytest.fixture
def fake_texts(monkeypatch):
    """Stub the DB reads of the word cloud; records the filters it was called with."""
    calls = {}

    def questions(db, house, year_from, year_to, session, subsidiary):
        calls["questions"] = (house, year_from, year_to, session, subsidiary)
        return ["Coking coal washeries", "Coking coal import", "Mine safety"]

    def documents(db, user, year_from, year_to, subsidiary):
        calls["documents"] = (user.org_unit.code, year_from, year_to, subsidiary)
        return ["Coking coal stock"]

    monkeypatch.setattr(topics_api, "_question_texts", questions)
    monkeypatch.setattr(topics_api, "_document_texts", documents)
    monkeypatch.setattr(topics_api, "_data_version", lambda db, source: ())
    topics_api._cache.clear()
    return calls


def test_every_role_can_see_the_word_cloud(client_as, fake_texts):
    for role in ("viewer", "operator", "reviewer", "analyst", "approver", "admin"):
        res = client_as([role]).get("/topics/wordcloud?house=LS&from=2019&to=2025")
        assert res.status_code == 200, role
    body = res.json()
    assert body["texts"] == 3
    assert body["words"][0] == {"text": "coking", "weight": 2}
    assert fake_texts["questions"] == (House.LOK_SABHA, 2019, 2025, None, None)
    assert "documents" not in fake_texts


def test_word_cloud_documents_source_and_filters(client_as, fake_texts):
    res = client_as(["viewer"], "SECL").get(
        "/topics/wordcloud?source=all&session=winter&subsidiary=SECL&from=2021"
    )
    assert res.status_code == 200
    assert res.json()["texts"] == 4
    assert fake_texts["questions"] == (None, 2021, None, "winter", "SECL")
    assert fake_texts["documents"] == ("SECL", 2021, None, "SECL")


def test_word_cloud_is_cached_by_filter(client_as, fake_texts):
    client = client_as(["viewer"])
    client.get("/topics/wordcloud?house=LS")
    fake_texts.clear()
    assert client.get("/topics/wordcloud?house=LS").status_code == 200
    assert fake_texts == {}  # served from the cache
    client.get("/topics/wordcloud?house=RS")
    assert fake_texts["questions"][0] == House.RAJYA_SABHA


def test_word_cloud_rejects_bad_filters(client_as, fake_texts):
    client = client_as(["viewer"])
    assert client.get("/topics/wordcloud?from=2025&to=2019").status_code == 422
    assert client.get("/topics/wordcloud?session=summer").status_code == 422
    assert client.get("/topics/wordcloud?house=XX").status_code == 422
    assert client.get("/topics/wordcloud?source=web").status_code == 422


def test_document_word_cloud_is_org_scoped(client_as):
    """The documents query carries the org-unit filter for a subsidiary user."""
    seen = []

    class Db:
        def execute(self, stmt):
            seen.append(str(stmt))
            return []

    from tests.conftest import fake_user

    topics_api._document_texts(Db(), fake_user(["viewer"], "SECL"), None, None, None)
    topics_api._document_texts(Db(), fake_user(["viewer"], "CIL_HQ"), None, None, None)
    assert "documents.org_unit_id" in seen[0]
    assert "documents.org_unit_id" not in seen[1]


def test_topics_need_login():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/topics").status_code == 401
    assert client.get("/topics/wordcloud").status_code == 401


def test_only_admin_can_rerun_topics(client_as, monkeypatch):
    for role in ("viewer", "operator", "reviewer", "analyst", "approver"):
        assert client_as([role]).post("/topics/refresh").status_code == 403, role

    class Db:
        def add(self, row):
            self.row = row

        def commit(self):
            pass

    from app.core.db import get_db
    from app.main import app

    monkeypatch.setattr(topics_api, "enqueue_topics_refresh", lambda force: force)
    client = client_as(["admin"])
    app.dependency_overrides[get_db] = lambda: Db()
    res = client.post("/topics/refresh")
    assert res.status_code == 200
    assert res.json() == {"queued": True}
