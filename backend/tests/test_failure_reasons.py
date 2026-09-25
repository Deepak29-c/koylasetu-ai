"""A failed document shows a reason a person can act on, never a traceback or a path (#70).

The worker used to store `f"{type(exc).__name__}: {exc}"` and the documents list showed
it verbatim, e.g. "FileNotFoundError: original file missing: storage/originals/2c/….pdf".
"""

import re
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.llm.client import ExternalCallBlocked, LlmUnavailable
from app.schemas.document import DocumentOut
from app.services import failures

SECRET = "storage/originals/2c/2cbd2d32057ff5ba80cef0a2916405009aeb62dee9bbf0942cfcf6a212d75ee9.pdf"
I18N = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "i18n.tsx"


class TesseractNotFoundError(OSError):
    """Stand-in with pytesseract's class name (the real one needs pytesseract imported)."""


class FileDataError(RuntimeError):
    """Stand-in with pymupdf's class name."""


@pytest.mark.parametrize(
    ("exc", "reason"),
    [
        (FileNotFoundError(f"original file missing: {SECRET}"), "file_missing"),
        (ValueError("No parser for application/zip"), "unsupported_file"),
        (FileDataError("Failed to open file"), "damaged_file"),
        (zipfile.BadZipFile("File is not a zip file"), "damaged_file"),
        (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), "damaged_file"),
        (TesseractNotFoundError("tesseract is not installed"), "ocr_unavailable"),
        (LlmUnavailable("connection refused"), "model_unavailable"),
        (ExternalCallBlocked("not a local URL"), "model_unavailable"),  # a subclass counts
        (ValueError("something else"), "unknown"),
        (KeyError("x"), "unknown"),
    ],
)
def test_each_kind_of_failure_gets_its_code(exc, reason):
    assert failures.classify(exc) == reason
    stored = failures.record(exc)
    assert stored.startswith(f"[{reason}] {type(exc).__name__}: ")  # detail kept for devs
    assert failures.reason_from_record(stored) == reason


@pytest.mark.parametrize(
    ("legacy", "reason"),
    [
        (f"FileNotFoundError: original file missing: {SECRET}", "file_missing"),
        ("ValueError: No parser for application/octet-stream", "unsupported_file"),
        ("TesseractNotFoundError: tesseract is not installed", "ocr_unavailable"),
        ("pymupdf.FileDataError: Failed to open file 'x.pdf'", "damaged_file"),
        ("LlmUnavailable: model server down", "model_unavailable"),
        ("RuntimeError: boom", "unknown"),
        ("a sentence with no exception name at all", "unknown"),
        ("[not_a_real_code] RuntimeError: boom", "unknown"),
    ],
)
def test_rows_written_before_the_change_still_map_safely(legacy, reason):
    assert failures.reason_from_record(legacy) == reason


def test_no_error_is_no_reason():
    assert failures.reason_from_record(None) is None
    assert failures.reason_from_record("  ") is None


def row(tmp_path, **extra) -> SimpleNamespace:
    kept = tmp_path / "kept.pdf"
    kept.write_bytes(b"%PDF")
    fields = dict(
        id=uuid.uuid4(),
        title="t",
        original_filename="t.pdf",
        doc_type="other",
        fy=None,
        org_unit_id=uuid.uuid4(),
        is_public=False,
        language="en",
        mime_type="application/pdf",
        size_bytes=4,
        status="PROCESSED",
        error_message=None,
        page_count=1,
        pages_done=1,
        source_url=None,
        created_at=datetime.now(UTC),
        file_path=str(kept),
    )
    fields.update(extra)
    return SimpleNamespace(**fields)


def test_the_api_never_sends_the_raw_error_or_the_path(tmp_path):
    doc = row(
        tmp_path,
        status="FAILED",
        error_message=f"FileNotFoundError: original file missing: {SECRET}",
        file_path=SECRET,
    )
    out = DocumentOut.model_validate(doc)
    body = out.model_dump_json()
    assert out.failure_reason == "file_missing"
    assert out.failure_message == failures.MESSAGES["file_missing"]
    for leak in (
        "FileNotFoundError",
        "storage/originals",
        "2cbd2d32",
        "error_message",
        "file_path",
    ):
        assert leak not in body
    assert "error_message" not in DocumentOut.model_json_schema(mode="serialization")["properties"]


def test_a_processed_document_whose_file_went_missing_says_so(tmp_path):
    out = DocumentOut.model_validate(row(tmp_path, file_path=str(tmp_path / "gone.pdf")))
    assert out.file_missing is True
    assert out.failure_reason == "file_missing"


def test_a_healthy_document_has_no_reason(tmp_path):
    out = DocumentOut.model_validate(row(tmp_path))
    assert out.file_missing is False
    assert out.failure_reason is None and out.failure_message is None


def test_a_failed_document_with_no_recorded_error_is_unknown(tmp_path):
    out = DocumentOut.model_validate(row(tmp_path, status="FAILED"))
    assert out.failure_reason == "unknown"


def test_every_reason_has_an_english_and_hindi_sentence_on_screen():
    """The frontend translates the code; a code without a label would show a raw key."""
    source = I18N.read_text(encoding="utf-8")
    english = source[source.index("const en = {") : source.index("export type LabelKey")]
    hindi = source[source.index("const hi") : source.index("export type Lang")]
    for code in (*failures.REASONS, "server_error"):
        for block in (english, hindi):
            assert re.search(rf'^\s{{2}}"failure\.{code}"\s*:', block, re.M), code
    assert set(failures.MESSAGES) == set(failures.REASONS)
