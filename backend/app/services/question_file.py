"""The plain text of a PQ file (PDF, Word or text), to fill the question box of the New PQ
reply screen. Nothing is stored: the caller deletes the temporary file afterwards.

The type is told from the content, as for uploads (services/file_types.py); a text file has
no magic bytes, so it is accepted by its .txt name when it holds UTF-8 text.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pymupdf

from app.services import file_types

log = logging.getLogger(__name__)

MAX_CHARS = 20000  # the question box takes this many characters (schemas/pq_reply.py)
_BLANK_RUN = re.compile(r"\n{3,}")


class NotAllowed(Exception):
    """Not a PDF, Word or text file."""


class Unreadable(Exception):
    """An allowed type that could not be opened (damaged, encrypted, not UTF-8)."""


class NoText(Exception):
    """The file opened but has no text, e.g. a scanned PDF without a text layer."""


def kind_of(path: Path, filename: str) -> str:
    """The kind as "pdf", "docx" or "txt"; NotAllowed for anything else."""
    with path.open("rb") as fh:
        head = fh.read(8192)
        kind = file_types.detect(head, filename, fh)
    if kind in (file_types.PDF, file_types.DOCX):
        return kind.ext
    if kind is None and filename.lower().endswith(".txt") and b"\x00" not in head:
        return "txt"
    raise NotAllowed


def _pdf_text(path: Path) -> str:
    pieces: list[str] = []
    size = 0
    with pymupdf.open(path) as doc:
        for page in doc:
            text = page.get_text("text")
            pieces.append(text)
            size += len(text)
            if size > MAX_CHARS:
                break
    return "\n".join(pieces)


def _docx_text(path: Path) -> str:
    import docx  # python-docx

    return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)


def _txt_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Unreadable from None


def tidy(text: str) -> str:
    """Line ends unified, trailing spaces dropped, runs of blank lines kept to one."""
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return _BLANK_RUN.sub("\n\n", "\n".join(lines)).strip()


def read_question(path: Path, filename: str) -> tuple[str, bool]:
    """(text, truncated). Raises NotAllowed, Unreadable or NoText."""
    kind = kind_of(path, filename)
    reader = {"pdf": _pdf_text, "docx": _docx_text, "txt": _txt_text}[kind]
    try:
        raw = reader(path)
    except Unreadable:
        raise
    except Exception as e:  # a damaged or encrypted file; the libraries raise many types
        log.info("Question file %s could not be read: %s", filename, type(e).__name__)
        raise Unreadable from None
    text = tidy(raw)
    if not text:
        raise NoText
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS].rstrip(), True
    return text, False
