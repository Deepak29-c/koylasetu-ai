"""eval/pq_benchmark.jsonl (issue #16): every line is in the format eval/run_eval.py reads and
every expected number is really in the official answer (checked by scripts/check_benchmark.py).
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_benchmark.py"
spec = importlib.util.spec_from_file_location("check_benchmark", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_benchmark_file_has_no_problems():
    entries, problems = check.check_file(check.DEFAULT_PATH)
    assert problems == []
    assert 30 <= len(entries) <= 50
    assert all(e["expected_numbers"] for e in entries)  # every question has figures to compare
    assert all(e["source_url"].startswith("https://coal.gov.in/") for e in entries)


def test_known_entry_matches_the_official_pdf():
    # LS Unstarred Q 1446 of 27.11.2019, checked by hand against the PDF
    entries, _ = check.check_file(check.DEFAULT_PATH)
    e = next(e for e in entries if e["id"] == "LS-2019-11-27-U1446")
    assert e["house"] == "LS" and e["date"] == "2019-11-27" and e["topic"] == "auction"
    assert {"value": 145.58, "unit": "MT"} in e["expected_numbers"]
    assert "the total quantity of coal imported was 145.58 MT (provisional)" in e["official_answer"]


@pytest.mark.parametrize(
    "value, text",
    [
        (42871, "is 42,871 Tonnes."),
        (428710, "about 4,28,710 tonnes"),  # Indian grouping
        (13.2, "13.20 MT as on 31.12.2017"),
        (0.66, "4.838 0.660"),
        (50.0, "total dispatch of 50.00 MT"),
        (-0.382, "1,308 -0.382 The sales"),
        (730.873, "is 730.873 Million Tonne."),
        (1085.0, "1085.00# Domestic"),
    ],
)
def test_number_found(value, text):
    assert check.number_in_text(value, text)


@pytest.mark.parametrize(
    "value, text",
    [
        (12, "112 rakes"),
        (12, "12.5 MT"),
        (12.5, "12.55 MT"),
        (730.87, "730.873 MT"),
        (4200, "42,000 tonnes"),
        (6, "6.563 MT"),
    ],
)
def test_number_not_found(value, text):
    assert not check.number_in_text(value, text)


def test_bad_entries_are_reported(tmp_path):
    good = {
        "id": "LS-2020-03-04-U2174",
        "house": "LS",
        "date": "2020-03-04",
        "question": "(a) whether ...",
        "official_answer": "pithead coal stock with CIL was 42.43 MT",
        "expected_numbers": [{"value": 42.43, "unit": "MT"}],
        "topic": "coal stock",
    }
    bad_number = {**good, "id": "x2", "expected_numbers": [{"value": 42.34, "unit": "MT"}]}
    no_topic = {k: v for k, v in good.items() if k != "topic"} | {"id": "x3"}
    bad_house = {**good, "id": "x4", "house": "Lok Sabha", "date": "04.03.2020"}
    path = tmp_path / "b.jsonl"
    lines = [json.dumps(e) for e in (good, bad_number, no_topic, bad_house, good)] + ["{oops"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    entries, problems = check.check_file(path)
    assert len(entries) == 5
    assert problems == [
        "line 2: expected_numbers[0] 42.34 MT is not in official_answer",
        "line 3: missing topic",
        "line 4: house should be LS or RS, got 'Lok Sabha'",
        "line 4: date should be YYYY-MM-DD, got '04.03.2020'",
        "line 5: duplicate id LS-2020-03-04-U2174",
        "line 6: not valid JSON (Expecting property name enclosed in double quotes)",
    ]
