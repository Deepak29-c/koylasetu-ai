"""Turn an uploaded file into pages of text blocks and tables (guide 7.1 steps 2-7).

No database code here, so every parser can be unit-tested on its own. Coordinates:
- PDF: PDF points (1/72 inch) on that page, the same space PyMuPDF uses to draw highlights.
- Images: pixels of the original image.
- Excel / CSV / DOCX: no page geometry, bbox is None.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from PIL import Image, ImageSequence

from app.services.normalise import OTHER, find_period, find_unit
from worker.ocr import OcrResult

BBox = list[float]  # [x0, y0, x1, y1]
OcrFn = Callable[[Image.Image], OcrResult]

SCANNED_TEXT_CHARS = 50  # guide 7.1 step 2: fewer characters than this -> treat as scanned
OCR_DPI = 300


@dataclass
class Block:
    text: str
    bbox: BBox | None = None


@dataclass
class Table:
    rows: list[list[str]]
    bbox: BBox | None = None
    title: str | None = None
    cell_bboxes: list[list[BBox | None]] | None = None  # same shape as rows


@dataclass
class PageResult:
    page_no: int  # 1-based; sheet number for spreadsheets
    has_text_layer: bool
    blocks: list[Block] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    ocr_used: bool = False
    ocr_confidence: float | None = None


def page_count(path: Path, mime: str) -> int:
    if mime == "application/pdf":
        with pymupdf.open(path) as doc:
            return doc.page_count
    if mime.startswith("image/"):
        with Image.open(path) as img:
            return getattr(img, "n_frames", 1)
    if mime in (SHEET_MIMES | {"text/csv"}):
        return len(_read_sheets(path, mime))
    return 1


def parse(path: Path, mime: str, ocr: OcrFn) -> Iterator[PageResult]:
    if mime == "application/pdf":
        yield from parse_pdf(path, ocr)
    elif mime.startswith("image/"):
        yield from parse_image(path, ocr)
    elif mime in SHEET_MIMES or mime == "text/csv":
        yield from parse_sheets(path, mime)
    elif mime == DOCX_MIME:
        yield from parse_docx(path)
    else:
        raise ValueError(f"No parser for {mime}")


# --- PDF -----------------------------------------------------------------------------------


def parse_pdf(path: Path, ocr: OcrFn) -> Iterator[PageResult]:
    with pymupdf.open(path) as doc:
        running = _running_header_lines(doc)
        for index, page in enumerate(doc):
            if len(page.get_text("text").strip()) < SCANNED_TEXT_CHARS:
                yield _ocr_pdf_page(page, index + 1, ocr)
            else:
                yield _digital_pdf_page(page, index + 1, running)


HEADER_BAND = 0.1  # top share of the page where running headers live


def _line_key(line: str) -> str:
    return " ".join(re.sub(r"[^a-z]+", " ", line.lower()).split())


def _running_header_lines(doc: pymupdf.Document) -> set[str]:
    """Lines repeated at the top of two or more pages ("Annual Report 2024-25 / Ministry of
    Coal"). Digits are ignored, so page numbers and years do not make lines look different."""
    seen: Counter[str] = Counter()
    for page in doc:
        band = page.rect.height * HEADER_BAND
        keys = {
            _line_key(line)
            for *box, text, _no, kind in page.get_text("blocks")
            if kind == 0 and box[3] <= band
            for line in text.splitlines()
        }
        seen.update(k for k in keys if k)
    return {k for k, n in seen.items() if n >= 2}


def _digital_pdf_page(
    page: pymupdf.Page, page_no: int, running_headers: set[str] | frozenset[str] = frozenset()
) -> PageResult:
    blocks = [
        Block(text.strip(), [round(v, 2) for v in (x0, y0, x1, y1)])
        for x0, y0, x1, y1, text, _no, kind in page.get_text("blocks", sort=True)
        if kind == 0 and text.strip()  # kind 0 = text, 1 = image
    ]
    titles = [b for b in blocks if not _is_running_header(b, running_headers)]
    tables = _pdf_tables(page, titles)
    return PageResult(page_no, has_text_layer=True, blocks=blocks, tables=tables)


TITLE_BAND = 60  # PDF points above a table searched for its title / unit note


def _round_box(box) -> BBox | None:
    return [round(v, 2) for v in box] if box else None


def _pdf_tables(page: pymupdf.Page, blocks: list[Block]) -> list[Table]:
    try:
        found = page.find_tables()
    except Exception:  # table detection is best effort; never fail the page because of it
        return []
    tables = []
    for t in found.tables:
        rows = [[_cell(c) for c in row] for row in t.extract()]
        if len(rows) >= 2 and any(any(c for c in row) for row in rows):
            boxes = [[_round_box(c) for c in row.cells] for row in t.rows]
            box = _round_box(t.bbox)
            tables.append(
                Table(rows, box, _with_page_date(_title_above(box, blocks), box, blocks), boxes)
            )
    return tables


# A heading line that is only a date, e.g. "(As on 01.04.2025)", printed once near the top of
# a page for every table below it (National Coal Inventory, Table IV).
_AS_ON_LINE = re.compile(r"\(?\s*as\s+on\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})\s*\)?", re.IGNORECASE)


def _with_page_date(title: str | None, box: BBox, blocks: list[Block]) -> str | None:
    """Add the page's "As on <date>" heading to a table title that names no period. Only
    when exactly one such date line is printed above the table; two different dates, or a
    date inside a sentence, change nothing."""
    if not find_period(title).empty:
        return title
    top = box[1]
    dates = {
        m.group(1)
        for b in blocks
        if b.bbox and b.bbox[3] <= top + 2
        for line in b.text.splitlines()
        if (m := _AS_ON_LINE.fullmatch(line.strip()))
    }
    if len(dates) != 1:
        return title
    return f"{title or ''} (As on {dates.pop()})".strip()


def _is_running_header(block: Block, running: set[str] | frozenset[str]) -> bool:
    """A repeated page header, unless it states a unit ("Fig. in MT") or an "As on" date
    ("(As on 01.04.2025)" on every page of the Coal Inventory): those are kept."""
    keys = [k for k in map(_line_key, block.text.splitlines()) if k]
    if not keys or not all(k in running for k in keys):
        return False
    if any(_AS_ON_LINE.fullmatch(line.strip()) for line in block.text.splitlines()):
        return False
    unit = find_unit(block.text)
    return unit is None or unit.kind == OTHER


def _title_above(box: BBox, blocks: list[Block]) -> str | None:
    """Text just above a table: its title and often its unit, e.g. "Coal Production (MT)"."""
    x0, top, x1, _ = box
    parts = [
        b.text
        for b in blocks
        if b.bbox
        and top - TITLE_BAND <= b.bbox[1]
        and b.bbox[3] <= top + 2
        and b.bbox[0] < x1
        and b.bbox[2] > x0
        and any(ch.isalpha() for ch in b.text)
    ]
    return " ".join(" ".join(parts).split())[:500] or None


def _ocr_pdf_page(page: pymupdf.Page, page_no: int, ocr: OcrFn) -> PageResult:
    pix = page.get_pixmap(dpi=OCR_DPI)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    result = ocr(image)
    scale = 72 / OCR_DPI  # OCR pixels -> PDF points
    blocks = [Block(line.text, [round(v * scale, 2) for v in line.bbox]) for line in result.lines]
    return PageResult(
        page_no,
        has_text_layer=False,
        blocks=blocks,
        ocr_used=True,
        ocr_confidence=result.confidence,
    )


# --- Images ----------------------------------------------------------------------------------


def parse_image(path: Path, ocr: OcrFn) -> Iterator[PageResult]:
    with Image.open(path) as img:
        for index, frame in enumerate(ImageSequence.Iterator(img)):  # multi-page TIFF
            result = ocr(frame.convert("RGB"))
            yield PageResult(
                index + 1,
                has_text_layer=False,
                blocks=[Block(line.text, line.bbox) for line in result.lines],
                ocr_used=True,
                ocr_confidence=result.confidence,
            )


# --- Excel / CSV -----------------------------------------------------------------------------

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLS_MIME = "application/vnd.ms-excel"
SHEET_MIMES = {XLSX_MIME, XLS_MIME}
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _read_sheets(path: Path, mime: str) -> dict[str, list[list[str]]]:
    import pandas as pd

    if mime == "text/csv":
        try:
            frames = {"CSV": pd.read_csv(path, header=None, dtype=str, encoding="utf-8-sig")}
        except UnicodeDecodeError:
            frames = {"CSV": pd.read_csv(path, header=None, dtype=str, encoding="cp1252")}
    else:
        frames = pd.read_excel(path, sheet_name=None, header=None, dtype=str)
    # Cells are kept exactly as text; numbers are never re-typed (guide 7.2).
    return {
        name: [[_cell(v) for v in row] for row in df.itertuples(index=False)]
        for name, df in frames.items()
    }


def parse_sheets(path: Path, mime: str) -> Iterator[PageResult]:
    """Every sheet is one table (guide 7.1 step 7). Its text for search comes from the table
    chunks (worker.embed.table_chunks), so no separate row text is added here."""
    for index, (name, rows) in enumerate(_read_sheets(path, mime).items()):
        rows = [r for r in rows if any(r)]
        tables = [Table(rows, title=str(name))] if rows else []
        yield PageResult(index + 1, has_text_layer=True, tables=tables)


# --- Word --------------------------------------------------------------------------------------


def parse_docx(path: Path) -> Iterator[PageResult]:
    import docx  # python-docx

    document = docx.Document(str(path))
    blocks = [Block(p.text.strip()) for p in document.paragraphs if p.text.strip()]
    tables = []
    for t in document.tables:
        rows = [[_cell(c.text) for c in row.cells] for row in t.rows]
        if rows:
            tables.append(Table(rows))
    # A .docx has no fixed pages; everything is page 1.
    yield PageResult(1, has_text_layer=True, blocks=blocks, tables=tables)


def _cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text.strip()
