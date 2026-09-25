"""scripts/load_sources.py and fetch_sources.py: the parts that need no network (issue #15).

The loader itself was run twice against a local API + Postgres: the first run created every
downloaded document, the second reported each one as a duplicate.
"""

import csv
import importlib.util
from collections import Counter
from pathlib import Path

from app.models.enums import DocType

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loader = _load("load_sources")
fetcher = _load("fetch_sources")

ROWS = [
    {"file": "data/raw/a.pdf", "title": "Shortage of Coal", "doc_type": "pq_answer", "fy": ""},
    {"file": "data/raw/b.pdf", "title": "Coal Inventory 2024", "doc_type": "coal_inventory"},
    {"file": "data/raw/c.xls", "title": "CEA Monthly Coal Report", "doc_type": "monthly_stats"},
    {"file": "data/raw/shortage.pdf", "title": "Coal Stock", "doc_type": "pq_answer"},
]  # fmt: skip


def test_doc_types_match_the_api():
    assert loader.DOC_TYPES == {t.value for t in DocType}


def test_select_rows_by_type_match_and_limit():
    assert len(loader.select_rows(ROWS)) == 4
    assert [r["file"] for r in loader.select_rows(ROWS, ["pq_answer"])] == [
        "data/raw/a.pdf",
        "data/raw/shortage.pdf",
    ]
    # match looks at the title and the file name, case-insensitively
    assert len(loader.select_rows(ROWS, match="SHORTAGE")) == 2
    assert loader.select_rows(ROWS, ["coal_inventory", "monthly_stats"], limit=1) == [ROWS[1]]
    assert loader.select_rows(ROWS, ["annual_report"]) == []


def test_form_fields_carry_provenance():
    row = {
        "file": "data/raw/ministry-of-coal/msg-dec24.pdf",
        "title": "Monthly Coal Statistics -  December 2024",
        "source_url": "https://coal.nic.in/sites/default/files/2025-01/msg-dec24.pdf",
        "doc_type": "monthly_stats",
        "fy": "FY 2024-25",
    }
    assert loader.form_fields(row) == {
        "doc_type": "monthly_stats",
        "language": "en",
        "is_public": "true",
        "fy": "FY 2024-25",
        "source_url": "https://coal.nic.in/sites/default/files/2025-01/msg-dec24.pdf",
        "title": "Monthly Coal Statistics - December 2024",
    }


def test_form_fields_leave_out_blanks_and_fix_unknown_types():
    fields = loader.form_fields({"file": "x.pdf", "doc_type": "press_release", "fy": " "}, False)
    assert fields == {"doc_type": "other", "language": "en", "is_public": "false"}
    assert loader.form_fields({"file": "x.pdf", "language": "hi"})["language"] == "hi"


def test_multipart_body_has_fields_and_file():
    body = loader.multipart_body(
        {"doc_type": "other", "title": "Coal – Stock"},
        'a"b.pdf',
        b"%PDF-1.7",
        "application/pdf",
        "B",
    )
    text = body.decode("utf-8")
    assert text.startswith("--B\r\n")
    assert 'name="doc_type"\r\n\r\nother\r\n' in text
    assert "Coal – Stock" in text
    assert (
        'name="files"; filename="a\'b.pdf"\r\nContent-Type: application/pdf\r\n\r\n%PDF-1.7' in text
    )
    assert text.endswith("--B--\r\n")


def test_outcome_and_summary():
    assert loader.outcome([{"result": "created", "document": {"id": "d1"}}]) == ("created", "id=d1")
    dup = [
        {"result": "duplicate", "document": None, "error": "This exact file was uploaded before"}
    ]
    assert loader.outcome(dup) == ("duplicate", "This exact file was uploaded before")
    assert loader.outcome([]) == ("error", "empty response")
    counts = Counter({"created": 3, "missing file": 1})
    assert loader.summary_line(counts) == (
        "3 created, 0 duplicate, 0 rejected, 1 missing file, 0 error"
    )


def test_sources_csv_rows_are_loadable():
    """Every row names a file under data/raw, an http(s) source and a known doc type."""
    rows = loader.read_sources()
    assert len(rows) >= 20
    kinds = Counter(Path(r["file"]).suffix.lower() for r in rows)
    assert kinds[".pdf"] and (kinds[".xls"] or kinds[".xlsx"] or kinds[".csv"])
    for row in rows:
        assert row["file"].startswith("data/raw/")
        assert row["source_url"].startswith(("https://", "http://"))
        assert row["doc_type"] in loader.DOC_TYPES
        assert len(row["sha256"]) == 64
        loader.form_fields(row)  # never raises
    with loader.SOURCES_CSV.open(newline="", encoding="utf-8") as f:
        assert csv.DictReader(f).fieldnames == fetcher.FIELDS


def test_downloader_checks_the_file_signature():
    ole2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    assert fetcher.looks_like_document(b"%PDF-1.4 ...", "a.pdf")
    assert fetcher.looks_like_document(ole2 + b"...", "monthCoal1-2026-Aug.xls")
    assert fetcher.looks_like_document(b"PK\x03\x04...", "t.xlsx")
    assert fetcher.looks_like_document(b"year,production\n2024,1047.5\n", "p.csv")
    # an HTML error or bot-check page saved under the document's name is refused
    assert not fetcher.looks_like_document(b"<!DOCTYPE html><html>", "t.xlsx")
    assert not fetcher.looks_like_document(b"<!DOCTYPE html><html>", "p.csv")
    assert not fetcher.looks_like_document(b"<html>", "a.pdf")
