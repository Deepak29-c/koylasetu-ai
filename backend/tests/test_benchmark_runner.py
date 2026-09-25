"""Benchmark runner (issue #11, guide 15.2): scoring on fixed answers, the report, and a full
run against the real FastAPI app with login working and the Q&A service mocked (no Ollama)."""

import importlib.util
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.core.security import hash_password
from app.llm.client import LlmUnavailable
from app.main import app
from app.services import qa
from app.services.retrieval import Passage

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_runner.py"
spec = importlib.util.spec_from_file_location("benchmark_runner", SCRIPT)
br = importlib.util.module_from_spec(spec)
sys.modules["benchmark_runner"] = br  # dataclasses need the module registered
spec.loader.exec_module(br)

ENTRY = {
    "id": "LS-2018-12-26-U2431",
    "topic": "supply to power",
    "question": "(a) whether Coal India has despatched 84% coal to power sector in October, 2018?",
    "official_answer": (
        "In the month of October 2018, the average daily dispatch by Coal India Limited to Power "
        "sector was 1.357 Million Tonnes (MT). The quantity of coal dispatched to Power sector "
        "from CIL during October, 2018 was 42.07 MT which was 84.2% of total dispatch of 50.00 "
        "MT from CIL. Coal dispatch to power sector in October, 2018 has grown by 6% over the "
        "dispatch of October, 2017 (39.7 MT)."
    ),
    "expected_numbers": [
        {"value": 1.357, "unit": "MT/day"},
        {"value": 42.07, "unit": "MT"},
        {"value": 84.2, "unit": "%"},
        {"value": 50.0, "unit": "MT"},
    ],
}


def ok(answer: str, **extra) -> dict:
    response = {"answer": answer, "grounded": True, "not_found": False, "latency_ms": 900}
    return {"ok": True, "response": response | extra, "error": None, "wall_ms": 950}


def results_of(expected: list[dict], answer: str) -> list[str]:
    entry = {**ENTRY, "expected_numbers": expected}
    return [c["result"] for c in br.score_question(entry, ok(answer))["expected"]]


# --- units and matching ----------------------------------------------------------------------


def test_every_benchmark_unit_has_a_conversion():
    assert set(br.EXPECTED_UNITS) == br.check_benchmark.UNITS


def test_full_answer_finds_every_figure_and_nothing_unsupported():
    answer = (
        "In October 2018 CIL sent on average 1.357 million tonnes of coal per day to power "
        "plants [C1]. Dispatch to power was 42.07 MT, 84.2 per cent of the total 50 MT [C1]."
    )
    s = br.score_question(ENTRY, ok(answer))
    assert s["status"] == "answered" and s["found"] == 4 and s["all_correct"]
    assert s["unsupported_numbers"] == []


@pytest.mark.parametrize(
    "value, unit, answer, result",
    [
        (42.07, "MT", "was 42.07 MT", "found"),
        (42.07, "MT", "was 42.28 MT", "found"),  # +0.5% (0.4999...): inside the tolerance
        (100, "MT", "was 100.4 MT", "found"),  # off by 0.4%
        (100, "MT", "was 100.6 MT", "missing"),  # off by 0.6%
        (100, "MT", "was 99.4 MT", "missing"),
        (0.42, "MT", "was 4.2 lakh tonnes", "found"),  # lakh tonnes -> MT
        (42.871, "thousand tonnes", "is 42,871 tonnes", "found"),  # tonnes -> thousand tonnes
        (428.71, "thousand tonnes", "about 4,28,710 tonnes", "found"),  # Indian grouping
        (4200, "tonnes/year", "less than 4,200 tonnes per annum", "found"),
        (27.18, "MTPA", "27.18 MT of annual coal linkage", "found"),  # rate only on one side
        (1.357, "MT/day", "1.357 MTPA", "wrong_unit"),  # per year vs per day
        (84.2, "%", "was 84.2 MT", "wrong_unit"),  # % must stay %
        (84.2, "%", "share 84.2 of the total", "missing"),  # a bare number is not a %
        (42.07, "MT", "was 42.07%", "wrong_unit"),
        (1200, "MW", "about 1.2 GW", "found"),
        (1.2, "GW", "about 1,200 MW", "found"),
        (1313, "Rs/tonne", "for FSA sales Rs.1,313 per tonne", "found"),
        (1313, "Rs/tonne", "priced at Rs 1,313", "found"),  # bare rupees
        (2000, "Rs crore", "an outlay of Rs 2,000 crore", "found"),
        (20, "Rs crore", "an outlay of Rs 2,000 lakh", "found"),
        (-0.382, "%", "growth fell by 0.382%", "found"),  # sign said in words
        (12, "count", "12 mines were allotted", "found"),
        (12, "count", "12 MT was produced", "wrong_unit"),
        (12, "count", "112 mines", "missing"),
        (15, "days", "stock for 15 days", "found"),
        (127.5, "BU", "127.5 billion units", "found"),
        (1.34, "MT/day", "1.34 million tonnes of coal per day", "found"),
    ],
)
def test_expected_figure_matching(value, unit, answer, result):
    assert results_of([{"value": value, "unit": unit}], answer) == [result]


def test_dates_and_citation_ids_are_not_figures():
    numbers = br.answer_numbers("Stock was 16.74 MT on 25.11.2021 [C2], see Table 3 [F1].")
    assert [(n.token, n.unit.kind) for n in numbers] == [("16.74", "mass")]


def test_unsupported_numbers_are_those_not_in_the_official_answer():
    s = br.score_question(ENTRY, ok("Dispatch to power was 42.07 MT, up from 40.2 MT [C1]."))
    assert s["found"] == 1 and not s["all_correct"]
    assert s["unsupported_numbers"] == ["40.2"]


def test_table_cells_count_as_system_numbers():
    table = {"columns": ["Figure", "Value"], "rows": [["dispatch to power", "42.07 MT"]]}
    s = br.score_question(ENTRY, ok("Figures are in the table below [F1].", table=table))
    assert [c["result"] for c in s["expected"]][:2] == ["missing", "found"]


def test_not_found_and_error_replies():
    nf = br.score_question(ENTRY, ok(qa.NOT_FOUND, not_found=True))
    assert nf["status"] == "not_found" and nf["found"] == 0 and nf["grounded"] is True
    err = {"ok": False, "response": None, "error": "model_unavailable: down", "wall_ms": 12}
    e = br.score_question(ENTRY, err)
    assert e["status"] == "error" and e["found"] == 0 and e["grounded"] is None
    assert e["unsupported_numbers"] == []


# --- summary, sheets, report ---------------------------------------------------------------------


def _row(status="answered", found=2, expected=4, topic="t", grounded=True, latency=1000, **kw):
    return {
        "id": kw.get("id", str(uuid.uuid4())),
        "topic": topic,
        "status": status,
        "found": found,
        "expected_count": expected,
        "all_correct": found == expected,
        "grounded": grounded if status != "error" else None,
        "unsupported_numbers": kw.get("unsupported", []),
        "latency_ms": latency if status != "error" else None,
        "wall_ms": (latency or 0) + 50,
        "error": kw.get("error"),
        "expected": [],
        "citations": kw.get("citations", []),
        "answer": "a",
    }


def test_summary_definitions():
    rows = [
        _row(found=4, expected=4, topic="a", latency=1000),
        _row(found=1, expected=4, topic="a", grounded=False, latency=3000, unsupported=["9"]),
        _row("not_found", found=0, expected=2, topic="b", latency=500),
        _row("error", found=0, expected=2, topic="b", error="timeout: no reply within 60 s"),
    ]
    s = br.summarise(rows)
    assert s["numeric_accuracy_pct"] == 41.7  # 5 of 12: errors and not-found count as misses
    assert s["numeric_accuracy_answered_pct"] == 62.5  # 5 of 8
    assert s["all_correct_pct"] == 25.0
    assert s["grounded_pct"] == 50.0  # of the 2 answered; not-found is left out
    assert (s["answered"], s["not_found"], s["errors"]) == (2, 1, 1)
    assert s["latency_ms"] == {"p50": 1000, "avg": 1500, "max": 3000}
    assert s["error_kinds"] == {"timeout": 1}
    assert s["by_topic"]["a"]["numeric_accuracy_pct"] == 62.5
    assert s["by_topic"]["b"]["numeric_accuracy_pct"] == 0.0
    assert s["unsupported_numbers"] == 1


def test_empty_run_gives_na_not_a_crash():
    s = br.summarise([])
    assert s["numeric_accuracy_pct"] is None and s["latency_ms"]["p50"] is None
    assert "n/a" in br.render_report(
        {"run_date": "2026-09-26", "base_url": "x", "benchmark_questions": 34, "timeout_s": 5},
        s,
        [],
    )


def test_citation_sheet_sample_and_scoring(tmp_path):
    cit = [{"id": "C1", "kind": "passage", "document": "Coal Directory", "page": 4, "text": "t"}]
    rows = [_row(id=f"Q{i:02d}", citations=cit) for i in range(30)] + [_row(id="QX")]
    sheet = br.citation_rows(rows)
    assert len(sheet) == 20 and "QX" not in {r["question_id"] for r in sheet}
    assert sheet == br.citation_rows(list(reversed(rows)))  # same pick every time
    path = tmp_path / "citation_check.csv"
    br.write_citation_sheet(path, sheet)
    assert br.citation_correctness(path) is None  # nothing filled in yet
    text = path.read_text(encoding="utf-8-sig").splitlines()
    filled = [text[0]] + [
        ln[: -len(",,")] + (",Y," if i % 4 else ",N,") for i, ln in enumerate(text[1:])
    ]
    path.write_text("\n".join(filled) + "\n", encoding="utf-8")
    assert br.citation_correctness(path) == {"checked": 20, "correct": 15, "pct": 75.0}


def test_time_saved(tmp_path):
    path = tmp_path / "trials.csv"
    path.write_text("id,manual_seconds,assisted_seconds\nA,1200,300\nB,1800,300\n")
    assert br.time_saved(path) == {"trials": 2, "manual_s": 3000, "assisted_s": 600, "pct": 80.0}


def test_report_lists_misses_units_and_errors():
    entry = {**ENTRY, "expected_numbers": ENTRY["expected_numbers"][1:3]}
    good = {"id": entry["id"], "topic": entry["topic"], "question": "q"} | br.score_question(
        entry, ok("It was 42.07% [C1].")
    )
    good |= {"latency_ms": 900, "wall_ms": 950, "error": None}
    bad = {"id": "LS-X", "topic": "coal stock", "question": "q", "latency_ms": None}
    bad |= br.score_question(entry, {"ok": False, "error": "model_unavailable: down"})
    bad |= {"error": "model_unavailable: down", "wall_ms": 5}
    meta = {"run_date": "2026-09-26", "base_url": "http://api", "benchmark_questions": 34}
    report = br.render_report(meta | {"timeout_s": 60}, br.summarise([good, bad]), [good, bad])
    assert "# Benchmark run 2026-09-26" in report
    assert "| Numeric accuracy (figures found / expected) | 0.0% (0 of 4) |" in report
    assert "42.07 MT [wrong unit]" in report and "84.2 %" in report
    assert "error: model_unavailable: down" in report
    assert "Errors by kind: model_unavailable: 1." in report
    assert "not checked yet" in report and "not counted (no --database-url)" in report


def test_select_entries_and_run_dir(tmp_path):
    entries = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    assert br.select_entries(entries, None, 2) == entries[:2]
    assert br.select_entries(entries, ["C", "A"], None) == [entries[0], entries[2]]
    with pytest.raises(SystemExit):
        br.select_entries(entries, ["Z"], None)
    assert br.new_run_dir(tmp_path, "2026-09-26").name == "2026-09-26"
    assert br.new_run_dir(tmp_path, "2026-09-26").name == "2026-09-26-2"


# --- end to end: the real app, login included, Q&A service mocked ---------------------------


class FakeDb:
    """Just enough session for /auth/login and the current-user lookup."""

    def __init__(self, user):
        self.user = user

    def scalar(self, _stmt):
        return self.user

    def get(self, _model, _id):
        return self.user

    def add(self, _obj):
        pass

    def commit(self):
        pass


@pytest.fixture
def api(monkeypatch):
    org = SimpleNamespace(id=uuid.uuid4(), code="CIL_HQ", name="CIL HQ", type="hq")
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="analyst@koylasetu.local",
        name="Demo Analyst",
        roles=["analyst"],
        is_active=True,
        password_hash=hash_password("pw"),
        org_unit_id=org.id,
        org_unit=org,
    )
    db = FakeDb(user)
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()


def fake_ask(entries):
    """Q&A service stand-in: a right answer, a not-found reply, and a model outage."""
    by_question = {e["question"]: e for e in entries}

    def ask(db, user, question):
        entry = by_question[question]
        if entry["id"] == entries[1]["id"]:
            text, not_found, citations = qa.NOT_FOUND, True, []
        elif entry["id"] == entries[2]["id"]:
            raise LlmUnavailable("model server not reachable")
        else:
            nums = entry["expected_numbers"]
            text = " ".join(f"{n['value']} {n['unit']} [C1]." for n in nums)
            not_found = False
            citations = [
                Passage("C1", uuid.uuid4(), uuid.uuid4(), "Answer PDF", 2, None, "passage text")
            ]
        return qa.Answer(
            qa_id=uuid.uuid4(),
            answer=text,
            route="TEXTUAL",
            citations=citations,
            grounded=True,
            unmatched_numbers=[],
            confidence="high",
            not_found=not_found,
            latency_ms=42,
        )

    return ask


def test_end_to_end_run_against_the_api(api, monkeypatch, tmp_path, capsys):
    entries = br.load_benchmark(br.check_benchmark.DEFAULT_PATH)
    # simple units only, so the fake answer "<value> <unit>" is readable by the scorer
    simple = [e for e in entries if {n["unit"] for n in e["expected_numbers"]} <= {"MT", "MW"}]
    chosen = simple[:4]
    monkeypatch.setattr(qa, "ask", fake_ask(chosen))
    ids = ",".join(e["id"] for e in chosen)

    run_dir = br.main(
        ["--ids", ids, "--password", "pw", "--out", str(tmp_path), "--timeout", "5"],
        client=TestClient(app),
    )

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert (summary["answered"], summary["not_found"], summary["errors"]) == (2, 1, 1)
    assert summary["error_kinds"] == {"model_unavailable": 1}
    expected = sum(len(e["expected_numbers"]) for e in chosen)
    right = sum(len(chosen[i]["expected_numbers"]) for i in (0, 3))
    assert summary["expected_numbers"] == expected and summary["found_numbers"] == right
    assert summary["numeric_accuracy_answered_pct"] == 100.0
    assert summary["grounded_pct"] == 100.0 and summary["latency_ms"]["max"] == 42
    assert summary["ids"] == [e["id"] for e in chosen] and summary["run_date"] == run_dir.name
    saved = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    assert saved["results"][2]["http_status"] == 503
    assert saved["results"][0]["citations"][0]["document"] == "Answer PDF"
    assert (run_dir / "report.md").read_text(encoding="utf-8").startswith("# Benchmark run")
    sheet = (run_dir / "citation_check.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(sheet) == 3  # header + one citation for each of the 2 answered questions
    assert "[1/4]" in capsys.readouterr().out

    # fill the sheet, then re-score without asking the API again
    rows = [sheet[0]] + [ln[: -len(",,")] + ",Y," for ln in sheet[1:]]
    (run_dir / "citation_check.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    br.main(["--rescore", str(run_dir)])
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["citations"] == {"checked": 2, "correct": 2, "pct": 100.0}
    assert "100.0% (2 of 2 citations)" in (run_dir / "report.md").read_text(encoding="utf-8")


def test_timeouts_and_connection_errors_are_recorded_and_the_run_goes_on():
    import httpx

    calls = []

    def handler(request):
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t", "refresh_token": "r"})
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow", request=request)
        if len(calls) == 2:
            raise httpx.ConnectError("refused", request=request)
        if len(calls) == 3:
            return httpx.Response(401, json={"detail": "expired"})  # re-login, then retry
        return httpx.Response(500, text="boom")

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api")
    session = br.ApiSession(client, "a@b", "pw")
    rows = br.run([ENTRY, ENTRY, ENTRY], session, timeout=1, log=lambda _m: None)
    assert [r["error"].split(":")[0] for r in rows] == ["timeout", "connection", "http_500"]
    assert len(calls) == 4 and all(r["status"] == "error" for r in rows)


def test_official_answers_score_themselves():
    """Sanity check of the unit reading on all 183 real figures: the official answer used as
    the system answer finds every figure, with no unsupported numbers. The one miss is a
    table cell "79" in a % column with no % sign: an expected % must be written as a %."""
    entries = br.load_benchmark(br.check_benchmark.DEFAULT_PATH)
    missed = []
    for e in entries:
        s = br.score_question(e, ok(e["official_answer"]))
        assert s["unsupported_numbers"] == []
        missed += [(e["id"], c["value"]) for c in s["expected"] if c["result"] != "found"]
    assert missed == [("LS-2019-12-11-U3749", 79)]


def test_help_text_renders(capsys):
    """argparse treats % in help strings as a format character; --help must not crash."""
    with pytest.raises(SystemExit) as exit_info:
        br.parse_args(["--help"])
    assert exit_info.value.code == 0
    assert "automation % (facts)" in capsys.readouterr().out
