"""PQ reply builder and export (guide 10.1-10.2). The Q&A service and the model are mocked."""

import io
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import docx
import pymupdf
import pytest
from sqlalchemy.dialects import postgresql

from app.llm import client
from app.models import AuditLog, ParliamentQuestion, Report, ReportCitation, ReportVersion
from app.models.enums import House, QuestionType, ReportStatus
from app.services import pq_reply, qa, report_export
from app.services.pq_reply import Part
from app.services.retrieval import Passage

BENCHMARK = Path(__file__).resolve().parents[2] / "eval" / "pq_benchmark.jsonl"

PQ_EN = """Will the Minister of COAL be pleased to state:
(a) the coal production of Northern Coalfields Limited (NCL) in December, 2024;
(b) whether the target for the month was achieved; and
(c) if so, the details thereof?"""

PQ_HI = """क्या कोयला मंत्री यह बताने की कृपा करेंगे कि:
(क) दिसंबर, 2024 में एनसीएल का कोयला उत्पादन कितना था;
(ख) क्या उस माह का लक्ष्य प्राप्त किया गया; और
(ग) यदि हां, तो तत्संबंधी ब्यौरा क्या है?"""


def passage(ref, title="Monthly Summary Dec 2024", page=1, text="NCL produced 12.70 MT."):
    return Passage(ref, uuid.uuid4(), uuid.uuid4(), title, page, None, text)


def fact(ref, who="NCL", value="12.70"):
    return SimpleNamespace(
        ref=ref,
        fact_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Coal Directory",
        page_no=7,
        bbox=[1, 2, 3, 4],
        who=who,
        period_text="Dec 2024",
        value_raw=value,
    )


def answer(text, citations=(), not_found=False, table=None, facts=(), passages=None):
    return SimpleNamespace(
        answer=text,
        citations=list(citations),
        passages=list(citations if passages is None else passages),
        not_found=not_found,
        table=table,
        facts=list(facts),
    )


def header(**kw):
    base = dict(
        house=House.LOK_SABHA,
        q_type=QuestionType.UNSTARRED,
        q_no="1234",
        answer_date=date(2025, 2, 12),
        mp_name="Shri A. B. Member",
        subject="Coal production by NCL",
        intro="",
    )
    return pq_reply.build_header(**(base | kw))


def block(text, citations, **kw):
    return pq_reply.build_block(
        Part("a", "x"), answer(text, citations, **kw), pq_reply.SourceRegistry(), annexure_no=1
    )


# --- splitting ----------------------------------------------------------------------------------


def test_split_english_parts():
    intro, parts = pq_reply.split_by_markers(PQ_EN)
    assert intro == "Will the Minister of COAL be pleased to state:"
    assert [p.label for p in parts] == ["a", "b", "c"]
    assert parts[0].text.startswith("the coal production of Northern Coalfields")
    assert parts[2].text == "if so, the details thereof?"


def test_split_hindi_parts():
    intro, parts = pq_reply.split_by_markers(PQ_HI)
    assert intro.startswith("क्या कोयला मंत्री")
    assert [p.label for p in parts] == ["क", "ख", "ग"]
    assert "एनसीएल" in parts[0].text


def test_split_single_line_and_out_of_sequence_markers():
    q = "state: (a) the steps taken (i) to raise output (ii) to cut imports; and (b) the result?"
    _, parts = pq_reply.split_by_markers(q)
    assert [p.label for p in parts] == ["a", "b"]
    assert "(i) to raise output (ii)" in parts[0].text  # sub-items stay inside part (a)


def test_split_markers_without_opening_bracket():
    # LS-2019-06-26-U786 is written like this
    q = "a) whether there is acute shortage of coal; b) if so, the details thereof; and c) steps?"
    _, parts = pq_reply.split_by_markers(q)
    assert [(p.label, p.text) for p in parts] == [
        ("a", "whether there is acute shortage of coal;"),
        ("b", "if so, the details thereof; and"),
        ("c", "steps?"),
    ]


def test_split_top_level_roman_numerals():
    q = "state: (i) the coal stock at power plants; (ii) the reasons; and (iii) the steps taken?"
    _, parts = pq_reply.split_by_markers(q)
    assert [p.label for p in parts] == ["i", "ii", "iii"]
    assert parts[2].text == "the steps taken?"


def test_marker_inside_word_is_not_a_part():
    _, parts = pq_reply.split_by_markers("Is coal India(a) ltd listed?")
    assert parts == []


def benchmark():
    return [json.loads(line) for line in BENCHMARK.read_text(encoding="utf-8").splitlines()]


def test_splitter_on_the_34_real_benchmark_questions():
    entries = benchmark()
    assert len(entries) == 34
    for e in entries:
        intro, parts = pq_reply.split_by_markers(e["question"])
        labels = [p.label for p in parts]
        assert len(parts) >= 2, e["id"]
        assert labels == [chr(ord("a") + i) for i in range(len(parts))], e["id"]
        # nothing lost: every part is copied from the question, and only the markers are gone
        question = " ".join(e["question"].split())
        assert all(p.text in question for p in parts), e["id"]
        kept = len(" ".join([intro] + [p.text for p in parts]).split())
        assert kept == len(question.split()) - len(parts), e["id"]
        # the official answer covers the same last part: "(a) to (c)" / "(c)"
        last = labels[-1]
        assert f"({last}" in e["official_answer"] or f"{last})" in e["official_answer"], e["id"]


def test_no_markers_uses_llm_split_and_checks_its_parts():
    q = "Will the Minister state the coal production in 2024 and the steps taken to raise it?"

    def llm(system, user, json_schema=None):
        assert json_schema is not None
        return json.dumps(
            {
                "parts": [
                    {"text": "the coal production in 2024"},
                    {"text": "the steps taken to raise it"},
                ]
            }
        )

    intro, parts, method = pq_reply.split_question(q, llm)
    assert method == "llm" and intro == ""
    assert [(p.label, p.text) for p in parts] == [
        ("a", "the coal production in 2024"),
        ("b", "the steps taken to raise it"),
    ]


@pytest.mark.parametrize(
    "parts",
    [
        ["total imports of lignite", "prices"],  # invented
        ["the coal production in 2024", "the steps not taken to raise it"],  # inserted "not"
        ["the steps taken to raise it", "the coal production in 2024"],  # reordered
    ],
)
def test_llm_split_must_copy_the_question_exactly(parts):
    q = "Will the Minister state the coal production in 2024 and the steps taken to raise it?"

    def llm(system, user, json_schema=None):
        return json.dumps({"parts": [{"text": t} for t in parts]})

    _, got, method = pq_reply.split_question(q, llm)
    assert method == "single" and got == [Part("", q)]


def test_llm_split_that_fails_falls_back_to_one_part():
    q = "Will the Minister state the coal production in 2024?"

    def down(*a, **k):
        raise client.LlmUnavailable("down")

    for llm in (down, lambda *a, **k: "not json"):
        _, parts, method = pq_reply.split_question(q, llm)
        assert method == "single"
        assert parts == [Part("", q)]


def test_markers_do_not_call_the_model():
    def boom(*a, **k):
        raise AssertionError("model called")

    assert pq_reply.split_question(PQ_EN, boom)[2] == "markers"


def test_dependent_part_carries_previous_part_and_subject():
    _, parts = pq_reply.split_by_markers(PQ_EN)
    q = pq_reply.part_query("Coal production", parts, 2)
    assert q.startswith("Coal production: whether the target")
    assert q.endswith("if so, the details thereof?")
    assert pq_reply.part_query(None, parts, 0) == parts[0].text


# --- only sourced figures survive ---------------------------------------------------------------


def test_unsupported_figure_sentence_is_dropped():
    b = block(
        "NCL produced 12.70 MT [C1]. This was 9.4% higher than last year [C1].", [passage("C1")]
    )
    assert b["text"] == "NCL produced 12.70 MT [S1]."
    assert b["removed_numbers"] == ["9.4"]
    assert block("Output rose by 9.4% [C1].", [passage("C1")])["not_found"]


def test_hindi_digit_figure_not_in_source_is_dropped():
    src = passage("C1", text="एनसीएल का उत्पादन 997.83 मिलियन टन था।")
    b = block("उत्पादन ९९७.८३ मिलियन टन था [C1]। लक्ष्य १२३४.५ मिलियन टन था [C1]।", [src])
    assert "१२३४.५" not in b["text"] and "९९७.८३" in b["text"]
    assert b["removed_numbers"] == ["1234.5"]


def test_figure_from_the_mps_question_is_not_a_source():
    # The MP asserts "84%"; the passage does not have it. qa.ask grounds against the question
    # too, so its answer can repeat the figure and pass; the draft must not.
    src = passage("C1", text="CIL supplied 1.2 MT per day to the power sector.")
    b = block("Yes, CIL despatched 84% coal to the power sector [C1].", [src])
    assert b["not_found"] and b["removed_numbers"] == ["84"]


def test_sentence_with_a_figure_but_no_citation_is_dropped():
    src = passage("C1", text="CIL supplies coal to power plants under FSAs.")
    b = block(
        "CIL supplies coal to power plants under FSAs [C1]. "
        "Despatch was 1.34 MT per day in October 2018.",
        [src],
    )
    assert b["text"] == "CIL supplies coal to power plants under FSAs [S1]."
    assert b["removed_numbers"] == ["1.34", "2018"]


def test_figure_must_be_in_the_source_it_cites_not_another_passage():
    c1 = passage("C1", text="Imports were 235 MT.")
    c2 = passage("C2", text="Production was 729 MT.")
    b = block("Production was 729 MT [C1].", [c1, c2])
    assert b["not_found"] and b["removed_numbers"] == ["729"]


def test_bullets_are_checked_one_by_one_and_can_use_the_lists_citation():
    src = passage("C1", text="NCL 12.70 MT; MCL 15.10 MT; SECL 16.20 MT")
    text = "Subsidiary-wise production:\n- NCL: 12.70 MT\n- MCL: 99.99 MT\n- SECL: 16.20 MT [C1]"
    b = block(text, [src])
    assert b["text"].splitlines() == [
        "Subsidiary-wise production:",
        "- NCL: 12.70 MT",
        "- SECL: 16.20 MT [S1]",
    ]
    assert b["removed_numbers"] == ["99.99"]


def test_abbreviations_do_not_split_and_markers_stay_with_their_sentence():
    src = passage("C1", text="M.C.L. produced 204.5 MT. Despatch was 190 MT.")
    b = block("M.C.L. produced 204.5 MT. [C1] Despatch was 190 MT. [C1]", [src])
    assert b["text"] == "M.C.L. produced 204.5 MT. [S1] Despatch was 190 MT. [S1]"
    assert pq_reply.sentences("M.C.L. produced 204.5 MT. [C1] Despatch was 190 MT.") == [
        "M.C.L. produced 204.5 MT. [C1]",
        "Despatch was 190 MT.",
    ]


# --- blocks, annexures, citations ---------------------------------------------------------------


def test_block_renumbers_citations_across_parts():
    reg = pq_reply.SourceRegistry()
    shared = passage("C1")
    other = passage("C1", title="Annual Report", page=33, text="Target 12.16 MT.")
    b1 = pq_reply.build_block(
        Part("a", "production"), answer("NCL produced 12.70 MT [C1].", [shared]), reg, annexure_no=1
    )
    # Same chunk comes back as C2 in the next answer: it keeps its reply-wide number S1.
    same_again = Passage(
        "C2", shared.chunk_id, shared.document_id, shared.document_title, 1, None, shared.text
    )
    b2 = pq_reply.build_block(
        Part("b", "target"),
        answer("The target was 12.16 MT [C1] and output 12.70 MT [C2].", [other, same_again]),
        reg,
        annexure_no=1,
    )
    assert b1["text"] == "NCL produced 12.70 MT [S1]."
    assert b2["text"] == "The target was 12.16 MT [S2] and output 12.70 MT [S1]."
    assert b2["citations"] == ["S2", "S1"]
    assert [s["id"] for s in reg.sources] == ["S1", "S2"]
    assert reg.sources[0]["parts"] == ["a", "b"]
    assert reg.sources[1]["page"] == 33 and reg.sources[1]["kind"] == "chunk"


def test_part_without_source_says_not_found():
    reg = pq_reply.SourceRegistry()
    nf = answer(qa.NOT_FOUND, not_found=True)
    uncited = answer("Yes, the target was achieved.")  # words but no source at all
    for a in (nf, uncited):
        b = pq_reply.build_block(Part("b", "x"), a, reg, annexure_no=1)
        assert b["text"] == pq_reply.NOT_FOUND_PART
        assert b["not_found"] and b["citations"] == []
    hindi = pq_reply.build_block(Part("ख", "x"), nf, reg, annexure_no=1, hindi=True)
    assert hindi["text"] == pq_reply.NOT_FOUND_PART_HI
    assert reg.sources == []


def test_small_table_stays_inline_large_table_goes_to_annexure():
    reg = pq_reply.SourceRegistry()
    few = [fact(f"F{i}") for i in range(1, 4)]
    small = {"columns": ["Company", "Value", "Source"], "rows": [[f.who, "1", f.ref] for f in few]}
    b = pq_reply.build_block(
        Part("a", "x"), answer("Figures [F1].", few[:1], table=small, facts=few), reg, annexure_no=1
    )
    assert b["annexure"] is None
    assert [r[2] for r in b["table"]["rows"]] == ["S1", "S2", "S3"]  # table refs renumbered
    assert b["citations"] == ["S1", "S2", "S3"]
    assert reg.sources[0]["kind"] == "fact" and reg.sources[0]["fact_id"]

    many = [fact(f"F{i}", who=f"CO{i}") for i in range(1, 9)]
    big = {"columns": ["Company", "Value", "Source"], "rows": [[f.who, "1", f.ref] for f in many]}
    text = "The coal production figures for Dec 2024 are given in the table below. [F1][F2]"
    b = pq_reply.build_block(
        Part("b", "x"), answer(text, many[:2], table=big, facts=many), reg, annexure_no=1
    )
    assert b["annexure"] == "Annexure-I"
    assert "for Dec 2024 are given in Annexure-I." in b["text"]
    assert len(b["table"]["rows"]) == 8


def test_annexures_are_numbered_and_links_point_at_facts_and_chunks():
    many = [fact(f"F{i}") for i in range(1, 9)]
    big = {"columns": ["C", "Source"], "rows": [[f.who, f.ref] for f in many]}
    answers = [
        answer("Figures [F1].", many[:1], table=big, facts=many),
        answer("NCL produced 12.70 MT [C1].", [passage("C1")]),
        answer("More figures [F1].", many[:1], table=big, facts=many),
    ]
    parts = [Part("a", "x"), Part("b", "y"), Part("c", "z")]
    draft = pq_reply.build_content(header(), parts, answers, hindi=False)
    blocks = draft.content["blocks"]
    assert [b["annexure"] for b in blocks] == ["Annexure-I", None, "Annexure-II"]
    assert "Details are given in Annexure-I." in blocks[0]["text"]
    chunk_links = [lk for lk in draft.links if lk["chunk_id"]]
    assert len(chunk_links) == 1 and chunk_links[0]["location_in_report"] == "part-b:S9"
    assert all((lk["fact_id"] is None) != (lk["chunk_id"] is None) for lk in draft.links)
    assert draft.links[0]["location_in_report"] == "Annexure-I:S1"
    assert len(draft.content["sources"]) == 9  # 8 facts shared by (a) and (c) + 1 chunk


def test_sources_are_rebuilt_from_links_in_reply_order():
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rows = [  # same created_at in the database: any order can come back
        ("part-c:S3", c, "Doc C", 9),
        ("Annexure-I:S1", a, "Doc A", 1),
        ("part-b:S2", b, "Doc B", 4),
        ("part-c:S1", a, "Doc A", 1),
        ("typed by hand", uuid.uuid4(), "Doc D", 2),
    ]
    assert pq_reply.sources_from_links(rows) == [
        {"id": "S1", "document": "Doc A", "page": 1},
        {"id": "S2", "document": "Doc B", "page": 4},
        {"id": "S3", "document": "Doc C", "page": 9},
        {"id": "S4", "document": "Doc D", "page": 2},
    ]


def test_plain_text_rendering_has_header_parts_answers_and_sources():
    draft = pq_reply.build_content(
        header(),
        [Part("a", "the production?"), Part("b", "the target?")],
        [
            answer("NCL produced 12.70 MT [C1].", [passage("C1")]),
            answer(qa.NOT_FOUND, not_found=True),
        ],
        hindi=False,
    )
    text = draft.content["text"]
    for line in (
        "LOK SABHA",
        "UNSTARRED QUESTION NO. 1234",
        "TO BE ANSWERED ON 12.02.2025",
        "COAL PRODUCTION BY NCL",
        "1234. SHRI A. B. MEMBER:",
        "(a) the production?",
        "ANSWER",
        "(a): NCL produced 12.70 MT [S1].",
        f"(b): {pq_reply.NOT_FOUND_PART}",
        "[S1] Monthly Summary Dec 2024, page 1",
    ):
        assert line in text
    assert pq_reply.DRAFT_LINE not in text and "removed as unsupported" not in text


def test_starred_question_gets_statement_layout():
    draft = pq_reply.build_content(
        header(q_type=QuestionType.STARRED),
        [Part("a", "x?"), Part("b", "y?"), Part("c", "z?")],
        [answer("NCL produced 12.70 MT [C1].", [passage("C1")])] * 3,
        hindi=False,
    )
    text = draft.content["text"]
    assert "(a) to (c): A Statement is laid on the Table of the House." in text
    assert (
        "Statement referred to in reply to parts (a) to (c) of Lok Sabha Starred Question "
        "No. 1234 for answer on 12.02.2025 asked by Shri A. B. Member"
    ) in text
    assert text.index("STATEMENT") < text.index("(a): NCL produced")


def fake_ask(db, user, question):
    return answer("NCL produced 12.70 MT [C1].", [passage("C1")])


def test_draft_reply_asks_the_qa_service_once_per_part():
    asked = []

    def ask(db, user, question):
        asked.append(question)
        return fake_ask(db, user, question)

    draft = pq_reply.draft_reply(
        None,
        None,
        house=House.RAJYA_SABHA,
        q_type=QuestionType.STARRED,
        q_no="55",
        answer_date=None,
        mp_name=None,
        subject="NCL",
        question_text=PQ_EN,
        ask=ask,
        llm=lambda *a, **k: "{}",
        check_model=lambda: None,
    )
    assert len(asked) == 3 and asked[0].startswith("NCL: the coal production")
    assert draft.split_method == "markers" and draft.content["warnings"] == []
    assert draft.content["header"]["house_label"] == "RAJYA SABHA"
    assert "STARRED QUESTION NO. 55" in draft.content["text"]


def test_more_than_max_parts_is_answered_up_to_the_limit_with_a_warning():
    q = " ".join(
        f"({chr(97 + i)}) the coal production of subsidiary number {i};" for i in range(12)
    )
    kw = dict(house=House.LOK_SABHA, q_type=QuestionType.UNSTARRED, q_no="1", answer_date=None)
    draft = pq_reply.draft_reply(
        None, None, **kw, mp_name=None, subject=None, question_text=q,
        ask=fake_ask, check_model=lambda: None,
    )  # fmt: skip
    assert len(draft.parts) == 12 and len(draft.content["blocks"]) == pq_reply.MAX_PARTS
    assert draft.content["warnings"] == [pq_reply.too_many_parts_warning(12)]


def test_model_down_is_raised_before_any_part_is_answered():
    def down():
        raise client.LlmUnavailable("no model")

    def ask(*a):
        raise AssertionError("asked")

    with pytest.raises(client.LlmUnavailable):
        pq_reply.draft_reply(
            None, None, house=House.LOK_SABHA, q_type=QuestionType.UNSTARRED, q_no=None,
            answer_date=None, mp_name=None, subject=None, question_text=PQ_EN,
            ask=ask, check_model=down,
        )  # fmt: skip


def test_ensure_available_checks_the_model_is_installed(monkeypatch):
    class Res:
        def __init__(self, code, body):
            self.status_code, self._body, self.text = code, body, ""

        def json(self):
            return self._body

    model = client.get_settings().llm_model
    monkeypatch.setattr(client.httpx, "get", lambda *a, **k: Res(200, {"models": []}))
    with pytest.raises(client.LlmUnavailable, match="not installed"):
        client.ensure_available()
    monkeypatch.setattr(
        client.httpx, "get", lambda *a, **k: Res(200, {"models": [{"name": model}]})
    )
    client.ensure_available()
    monkeypatch.setattr(client.httpx, "get", lambda *a, **k: Res(404, {}))  # not Ollama
    client.ensure_available()


# --- export -------------------------------------------------------------------------------------


def sample_content(q_type=QuestionType.UNSTARRED):
    many = [fact(f"F{i}", who=f"CO{i}") for i in range(1, 9)]
    big = {"columns": ["Company", "Value", "Source"], "rows": [[f.who, "1", f.ref] for f in many]}
    return pq_reply.build_content(
        header(q_type=q_type),
        [Part("a", "the production of NCL?"), Part("b", "subsidiary-wise?"), Part("c", "why?")],
        [
            answer("NCL produced 12.70 MT [C1]. It was 14.2% above target [C1].", [passage("C1")]),
            answer("Figures are given in the table below. [F1]", many[:1], table=big, facts=many),
            answer(qa.NOT_FOUND, not_found=True),
        ],
        hindi=False,
        warnings=["Example warning"],
    ).content


def sample_report(status=ReportStatus.DRAFT, content=None):
    return SimpleNamespace(
        title="LS Q 1234", status=status, content_json=content or sample_content()
    )


def docx_text(data: bytes) -> str:
    d = docx.Document(io.BytesIO(data))
    cells = [c.text for t in d.tables for r in t.rows for c in r.cells]
    return "\n".join([p.text for p in d.paragraphs] + cells)


def export_docx(report, pq_header=None, db_sources=()):
    items = report_export.items_for_report(report, pq_header, list(db_sources))
    return docx_text(report_export.to_docx(items))


def test_docx_export_contains_layout_parts_annexure_and_sources():
    text = export_docx(sample_report())
    for expected in (
        pq_reply.DRAFT_LINE,
        "Example warning",
        "MINISTRY OF COAL",
        "LOK SABHA",
        "UNSTARRED QUESTION NO. 1234",
        "TO BE ANSWERED ON 12.02.2025",
        "(a) the production of NCL?",
        "ANSWER",
        "(a): NCL produced 12.70 MT [S1].",
        "[figure(s) removed as unsupported: 14.2]",
        "(b): Figures are given in Annexure-I. [S2]",
        f"(c): {pq_reply.NOT_FOUND_PART}",
        "ANNEXURE-I",
        "Referred to in reply to part (b) of Lok Sabha Unstarred Question No. 1234",
        "CO8",  # annexure table rows
        pq_reply.SOURCES_HEADING,
        "[S1] Monthly Summary Dec 2024, page 1",
        "[S2] Coal Directory, page 7",
    ):
        assert expected in text, expected


def test_approved_export_has_no_internal_notes():
    text = export_docx(sample_report(ReportStatus.APPROVED))
    assert pq_reply.DRAFT_LINE not in text
    assert "removed as unsupported" not in text and "Example warning" not in text


def test_starred_export_has_the_statement():
    text = export_docx(sample_report(content=sample_content(QuestionType.STARRED)))
    assert "(a) to (c): A Statement is laid on the Table of the House." in text
    assert "STATEMENT" in text


def test_text_saved_by_the_plain_editor_is_exported_without_duplicates():
    # Exactly what the #31 editor saves on Save / Submit: {"text": <render_text output>}
    content = sample_content()
    saved = {"text": content["text"]}
    db_sources = [
        {"id": "S1", "document": "Monthly Summary Dec 2024", "page": 1},
        {"id": "S2", "document": "Coal Directory", "page": 7},
    ]
    text = export_docx(sample_report(ReportStatus.APPROVED, saved), header(), db_sources)
    assert text.count("GOVERNMENT OF INDIA") == 1
    assert text.count(pq_reply.SOURCES_HEADING) == 1
    assert text.count("UNSTARRED QUESTION NO. 1234") == 1
    assert "(a): NCL produced 12.70 MT [S1]." in text
    assert "CO8" in text  # "a | b" lines become a table again
    d = docx.Document(io.BytesIO(report_export.to_docx(
        report_export.items_for_report(sample_report(ReportStatus.APPROVED, saved), header(), [])
    )))  # fmt: skip
    assert len(d.tables) == 1 and d.tables[0].rows[8].cells[0].text == "CO8"


def test_short_edited_text_gets_header_and_db_sources_added():
    report = sample_report(ReportStatus.IN_REVIEW, {"text": "(a): Edited [S1]."})
    text = export_docx(report, header(), [{"id": "S1", "document": "Annual Report", "page": 3}])
    assert "UNSTARRED QUESTION NO. 1234" in text
    assert "(a): Edited [S1]." in text
    assert "[S1] Annual Report, page 3" in text
    assert pq_reply.DRAFT_LINE in text


def test_pdf_export_is_a_valid_pdf_with_the_reply():
    items = report_export.items_for_report(sample_report(), None, [])
    pdf = pymupdf.open("pdf", report_export.to_pdf(items))
    text = "".join(page.get_text() for page in pdf)
    assert "UNSTARRED QUESTION NO. 1234" in text
    assert "NCL produced 12.70 MT" in text
    assert "ANNEXURE-I" in text and "Coal Directory, page 7" in text


# --- endpoints ----------------------------------------------------------------------------------


class FakeSession:
    """Just enough of a Session for the endpoints: ids on flush, timestamps on refresh, and
    `scalar` answering the idempotency lookup from what was added."""

    def __init__(self):
        self.added = []
        self.statements = []

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    def commit(self):
        self.flush()

    def refresh(self, obj):
        obj.created_at = obj.updated_at = datetime(2026, 9, 26)

    def scalar(self, stmt):
        self.statements.append(stmt)
        sql = str(
            stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        for obj in self.added:
            key = isinstance(obj, Report) and obj.content_json.get("idempotency_key")
            if key and f"'{key}'" in sql:
                return obj
        return None


PQ_BODY = {
    "house": "LS",
    "q_type": "unstarred",
    "q_no": "1234",
    "answer_date": "2025-02-12",
    "mp_name": "Shri A. B. Member",
    "subject": "Coal production by NCL",
    "question_text": PQ_EN,
}


@pytest.fixture
def analyst(client_as, monkeypatch):
    from app.core.db import get_db
    from app.main import app

    monkeypatch.setattr(client, "ensure_available", lambda: None)
    session = FakeSession()
    http = client_as(["analyst"])
    app.dependency_overrides[get_db] = lambda: session
    return http, session


def test_viewer_cannot_draft(client_as):
    assert client_as(["viewer"]).post("/pq-replies/draft", json=PQ_BODY).status_code == 403


def test_reviewer_cannot_export(client_as):
    rid = "00000000-0000-0000-0000-000000000001"
    assert client_as(["reviewer"]).get(f"/reports/{rid}/export").status_code == 403


def test_analyst_draft_saves_pq_report_versions_and_citations(analyst, monkeypatch):
    http, session = analyst

    def ask(db, user, question):
        if "details thereof" in question:
            return answer(qa.NOT_FOUND, not_found=True)
        return fake_ask(db, user, question)

    monkeypatch.setattr(qa, "ask", ask)
    res = http.post("/pq-replies/draft", json=PQ_BODY)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["split_method"] == "markers"
    report = body["report"]
    assert report["status"] == "DRAFT" and report["report_type"] == "pq_reply"
    assert report["title"] == "Lok Sabha Unstarred Q. No. 1234: Coal production by NCL"
    blocks = report["content_json"]["blocks"]
    assert [b["part"] for b in blocks] == ["a", "b", "c"]
    assert blocks[2]["text"] == pq_reply.NOT_FOUND_PART
    assert "text" in report["content_json"]

    kinds = [type(o) for o in session.added]
    assert kinds.count(ParliamentQuestion) == 1 and kinds.count(Report) == 1
    assert kinds.count(ReportVersion) == 1
    citations = [o for o in session.added if isinstance(o, ReportCitation)]
    assert len(citations) == 2  # parts (a) and (b)
    assert all(isinstance(c.chunk_id, uuid.UUID) and c.fact_id is None for c in citations)
    assert [c.location_in_report for c in citations] == ["part-a:S1", "part-b:S2"]
    pq = next(o for o in session.added if isinstance(o, ParliamentQuestion))
    assert [p["label"] for p in pq.parts_json] == ["a", "b", "c"]
    audit_rows = [o for o in session.added if isinstance(o, AuditLog)]
    assert audit_rows[0].action == "create_pq_draft"


def test_retry_with_the_same_idempotency_key_returns_the_first_draft(analyst, monkeypatch):
    http, session = analyst
    calls = []

    def ask(db, user, question):
        calls.append(question)
        return fake_ask(db, user, question)

    monkeypatch.setattr(qa, "ask", ask)
    key = {"Idempotency-Key": str(uuid.uuid4())}
    first = http.post("/pq-replies/draft", json=PQ_BODY, headers=key)
    second = http.post("/pq-replies/draft", json=PQ_BODY, headers=key)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["report"]["id"] == second.json()["report"]["id"]
    assert [type(o) for o in session.added].count(Report) == 1
    assert len(calls) == 3  # the retry did not generate again


def test_draft_when_model_is_down_is_503_and_saves_nothing(client_as, monkeypatch):
    from app.core.db import get_db
    from app.main import app

    def down():
        raise client.LlmUnavailable("model server not reachable at http://10.0.0.5:11434")

    monkeypatch.setattr(client, "ensure_available", down)
    session = FakeSession()
    http = client_as(["approver"])
    app.dependency_overrides[get_db] = lambda: session
    res = http.post("/pq-replies/draft", json=PQ_BODY)
    assert res.status_code == 503
    assert "10.0.0.5" not in res.json()["detail"]  # no internal address shown to the user
    assert session.added == []


def test_export_is_scoped_to_the_users_unit(client_as):
    from app.api.pq_replies import export_statement
    from app.core.db import get_db
    from app.main import app

    session = FakeSession()
    http = client_as(["analyst"], "NCL")
    app.dependency_overrides[get_db] = lambda: session
    rid = uuid.uuid4()
    assert http.get(f"/reports/{rid}/export").status_code == 404  # not in this unit
    where = str(session.statements[0].whereclause.compile(dialect=postgresql.dialect()))
    assert "reports.org_unit_id" in where

    hq = SimpleNamespace(org_unit=SimpleNamespace(code="CIL_HQ"), org_unit_id=uuid.uuid4())
    where = export_statement(rid, hq).whereclause.compile(dialect=postgresql.dialect())
    assert "org_unit_id" not in str(where)  # CIL HQ sees every unit


def test_only_an_approved_report_becomes_exported():
    """Exporting a draft is a preview; it must not look like the end of the workflow."""
    from app.api.pq_replies import status_after_export

    assert status_after_export(ReportStatus.APPROVED) is ReportStatus.EXPORTED
    for unchanged in (
        ReportStatus.DRAFT,
        ReportStatus.IN_REVIEW,
        ReportStatus.RETURNED,
        ReportStatus.EXPORTED,
    ):
        assert status_after_export(unchanged) is unchanged
