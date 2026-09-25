"""Why a document failed, as a short code a person can act on (#70).

The worker used to store the raw exception text ("FileNotFoundError: original file
missing: storage/originals/2c/2cbd….pdf") and the documents list showed it as-is: a
Python class name and a server path on an officer's screen, in no language they read.

Now the full technical text stays in `Document.error_message`, which the API never
returns, and the browser only gets one of the codes below; the frontend shows the
matching sentence in English or Hindi (`failure.<code>` in frontend/src/lib/i18n.tsx).

The worker prefixes what it stores with the code ("[file_missing] FileNotFoundError: …"),
so reading it back is exact. Rows written before this change have no prefix; for those the
code is worked out from the exception name at the front of the text, so old failures
still display safely without a migration.

Pure functions only: no database, and no import of pymupdf / pytesseract / Pillow (the
exceptions are recognised by class name).
"""

import re
from pathlib import Path
from typing import Literal, get_args

FailureReason = Literal[
    "file_missing",
    "unsupported_file",
    "damaged_file",
    "ocr_unavailable",
    "model_unavailable",
    "unknown",
]
REASONS: tuple[FailureReason, ...] = get_args(FailureReason)

# The English sentence for each code. The frontend has its own (translated) copy keyed
# `failure.<code>`; this one is for API clients and log lines.
MESSAGES: dict[FailureReason, str] = {
    "file_missing": "The uploaded file could not be found on the server. Please upload it again.",
    "unsupported_file": (
        "This type of file cannot be read. Upload a PDF, Excel, image or Word file."
    ),
    "damaged_file": "The file is damaged or could not be opened. Please upload a fresh copy.",
    "ocr_unavailable": (
        "The text-reading (OCR) engine is not available on the server. "
        "Ask the administrator, then use Retry."
    ),
    "model_unavailable": (
        "The local AI model server was not available. Use Retry once it is running."
    ),
    "unknown": "Processing failed. Use Retry; if it fails again, tell the administrator.",
}

# Exception class names (anywhere in the class hierarchy) -> reason.
_BY_CLASS: dict[str, FailureReason] = {
    "FileNotFoundError": "file_missing",
    "TesseractNotFoundError": "ocr_unavailable",
    "TesseractError": "ocr_unavailable",
    "LlmUnavailable": "model_unavailable",
    "ExternalCallBlocked": "model_unavailable",
    "FileDataError": "damaged_file",  # pymupdf: not a valid PDF
    "EmptyFileError": "damaged_file",  # pymupdf
    "UnidentifiedImageError": "damaged_file",  # Pillow
    "DecompressionBombError": "damaged_file",  # Pillow
    "BadZipFile": "damaged_file",  # a broken XLSX / DOCX
    "InvalidFileException": "damaged_file",  # openpyxl
    "XLRDError": "damaged_file",  # xlrd (old .xls)
    "PackageNotFoundError": "damaged_file",  # python-docx
    "UnicodeDecodeError": "damaged_file",  # a CSV in an unreadable encoding
}

_PREFIX = re.compile(r"^\[([a-z_]+)\]\s*")
# "SomeError: detail" - the shape the worker has always written.
_CLASS_AT_START = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*:")


def _reason(class_names: list[str], detail: str) -> FailureReason:
    for name in class_names:
        if name in _BY_CLASS:
            return _BY_CLASS[name]
    if detail.startswith("No parser for"):  # worker/parse.py: a MIME type nothing reads
        return "unsupported_file"
    return "unknown"


def classify(exc: BaseException) -> FailureReason:
    """The reason code for an exception raised while processing a document."""
    names = [cls.__name__ for cls in type(exc).__mro__]
    return _reason(names, str(exc))


def record(exc: BaseException) -> str:
    """The text the worker stores in `Document.error_message`: code first, then the full
    technical detail for developers (never sent to the browser)."""
    return f"[{classify(exc)}] {type(exc).__name__}: {exc}"[:2000]


def reason_from_record(error_message: str | None) -> FailureReason | None:
    """Read the code back from a stored `error_message`, including legacy rows with no
    code prefix. None when there is no error."""
    if not error_message or not error_message.strip():
        return None
    text = error_message.strip()
    prefixed = _PREFIX.match(text)
    if prefixed:
        code = prefixed.group(1)
        return code if code in REASONS else "unknown"  # type: ignore[return-value]
    named = _CLASS_AT_START.match(text)
    if named:
        name = named.group(1).rsplit(".", 1)[-1]
        return _reason([name], text[named.end() :].strip())
    return "unknown"


def original_is_missing(file_path: str | None) -> bool:
    """True when the document's original file is not on disk (e.g. STORAGE_DIR moved)."""
    return not file_path or not Path(file_path).is_file()
