import io
import zipfile

from app.services import file_types as ft


def _zip(*names: str) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, "x")
    buf.seek(0)
    return buf


def test_magic_bytes_beat_extension():
    assert ft.detect(b"%PDF-1.7 ...", "report.xlsx") is ft.PDF
    assert ft.detect(b"\x89PNG\r\n\x1a\n....", "scan.pdf") is ft.PNG
    assert ft.detect(b"\xff\xd8\xff\xe0", "page.jpg") is ft.JPG
    assert ft.detect(b"II*\x00....", "page.tif") is ft.TIFF


def test_zip_formats_detected_from_contents():
    xlsx = _zip("[Content_Types].xml", "xl/workbook.xml")
    assert ft.detect(xlsx.getvalue()[:8], "a.bin", xlsx) is ft.XLSX
    docx = _zip("[Content_Types].xml", "word/document.xml")
    assert ft.detect(docx.getvalue()[:8], "a.xlsx", docx) is ft.DOCX
    other = _zip("payload.exe")
    assert ft.detect(other.getvalue()[:8], "a.xlsx", other) is None


def test_csv_and_xls():
    assert ft.detect(b"subsidiary,2023-24\nMCL,1\n", "prod.csv") is ft.CSV
    assert ft.detect(b"a,b\x00c", "prod.csv") is None
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 8
    assert ft.detect(ole, "old.xls") is ft.XLS
    assert ft.detect(ole, "old.doc") is None


def test_rejects_executables_and_scripts():
    assert ft.detect(b"MZ\x90\x00", "report.pdf") is None
    assert ft.detect(b"<script>alert(1)</script>", "x.html") is None
