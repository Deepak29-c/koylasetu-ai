"""Detect upload file type from its content, not its extension (guide section 14)."""

import io
import zipfile
from dataclasses import dataclass


@dataclass(frozen=True)
class FileKind:
    ext: str
    mime: str


PDF = FileKind("pdf", "application/pdf")
PNG = FileKind("png", "image/png")
JPG = FileKind("jpg", "image/jpeg")
TIFF = FileKind("tiff", "image/tiff")
XLSX = FileKind("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
DOCX = FileKind("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
XLS = FileKind("xls", "application/vnd.ms-excel")
CSV = FileKind("csv", "text/csv")

_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def detect(
    head: bytes, filename: str, open_file: io.BufferedIOBase | None = None
) -> FileKind | None:
    """Return the file kind, or None if it is not an allowed type.

    `head` is the first few KB of the file. `open_file` is needed for ZIP-based formats
    (xlsx / docx), whose type can only be told from the names inside the archive.
    """
    name = filename.lower()
    if head.startswith(b"%PDF-"):
        return PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head.startswith(b"\xff\xd8\xff"):
        return JPG
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return TIFF
    if head.startswith(b"PK\x03\x04") and open_file is not None:
        try:
            names = zipfile.ZipFile(open_file).namelist()
        except zipfile.BadZipFile:
            return None
        if any(n.startswith("xl/") for n in names):
            return XLSX
        if any(n.startswith("word/") for n in names):
            return DOCX
        return None
    # OLE2 is also used by old .doc/.ppt, so only accept it for .xls names.
    if head.startswith(_OLE2) and name.endswith(".xls"):
        return XLS
    # CSV has no magic bytes: accept plain text with a .csv name.
    if name.endswith(".csv") and b"\x00" not in head:
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as e:
            # The head may cut a multi-byte character in half at the very end.
            if e.start < len(head) - 4:
                return None
        return CSV
    return None
