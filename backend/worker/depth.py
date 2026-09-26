"""Depth-wise coal resources by state (#97), read from the National Coal Inventory's
"STATE-WISE AND DEPTH-WISE RESOURCE OF INDIAN COAL" table (Table II).

Read from the PDF's text layer line by line, not from the extracted tables: PyMuPDF's
table finder drops some pages of this table (West Bengal's rows on page 11 of the 2025
inventory came through as a header only), and runs other rows together into one cell.

A printed line looks like
    STATE / TOTAL FOR <state> / GRAND TOTAL, coal type, depth, Measured, Indicated,
    Inferred (exploration)[, Inferred (mapping)], Total
and state and coal type are only printed on the first line of their block. Every value is
copied as printed. We would rather skip a row than store it with the wrong meaning, so:
- a row is kept only if Measured + Indicated + Inferred = Total;
- a block's depth bands must add up to its total row (e.g. 0-300 + 300-600 + 600-1200 =
  0-1200), otherwise the whole block is dropped.
"0-600" is a depth band for Jharia (the only coalfield without a 0-300/300-600 split) but a
block total elsewhere (0-300 + 300-600); the sum check tells them apart.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import DepthResource, Document
from app.services.normalise import _STATES, match_state

log = logging.getLogger(__name__)

TITLE = re.compile(
    r"STATE\s*-?\s*WISE\s+AND\s+DEPTH\s*-?\s*WISE\s+RESOURCE\s+OF\s+INDIAN\s+COAL", re.I
)
AS_ON = re.compile(r"as\s+on\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", re.I)
DEPTH = re.compile(r"^(\d{1,4})\s*-\s*(\d{1,4})\*?$")
NUMBER = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
DECIMAL = re.compile(r"^\d[\d,]*\.\d+$")
# At the end of the text before the depth; the PDF sometimes runs the state name into it
# ("MADHYA PRADESHMEDIUM COKING"), so no space is required in front.
COAL_TYPE = re.compile(
    r"(prime\s+coking|medium\s+coking|semi\s*-?\s*coking|non\s*-?\s*coking(?:\s+coal)?"
    r"|high\s+sulphur|coking(?:\s+coal)?)\s*$",
    re.I,
)
TOTAL_FOR = re.compile(r"^total\s+for\s+(.+)$", re.I)
GRAND = re.compile(r"^grand\s+total$", re.I)
SECTIONS = {"GONDWANA", "TERTIARY"}
# Rounding in the printed table: a total may differ from its parts by a few hundredths
TOLERANCE = 0.06


@dataclass
class Line:
    """One printed line: its words left to right, and where it is on the page."""

    words: list[str]
    bbox: list[float]
    page_no: int


@dataclass
class DepthRow:
    page_no: int
    bbox: list[float]
    section: str | None
    state: str | None  # None = all India (GRAND TOTAL)
    coal_type: str | None  # None on TOTAL FOR / GRAND TOTAL rows
    depth_range: str
    values_raw: list[str]
    measured: float
    indicated: float
    inferred: float
    total: float
    is_total: bool = False

    @property
    def span(self) -> tuple[int, int]:
        a, b = DEPTH.match(self.depth_range).groups()
        return int(a), int(b)


@dataclass
class _Block:
    section: str | None
    state: str | None
    coal_type: str | None
    rows: list[DepthRow] = field(default_factory=list)


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE + abs(b) * 1e-5


def state_of(text: str) -> str | None:
    """Standard state name; the table cuts long names short ("ARUNACHAL PRAD")."""
    if state := match_state(text):
        return state
    key = re.sub(r"[^a-z]", "", text.lower())
    if len(key) < 6:
        return None
    hits = [s for s in _STATES if re.sub(r"[^a-z]", "", s.lower()).startswith(key)]
    return hits[0] if len(hits) == 1 else None


def _values(numbers: list[str]) -> tuple[float, float, float, float] | None:
    """(measured, indicated, inferred, total) if the printed row adds up, else None.
    4 numbers: M, I, Inferred, Total; 5: M, I, Inferred (exploration), (mapping), Total."""
    if len(numbers) not in (4, 5):
        return None
    v = [_num(n) for n in numbers]
    m, i, total = v[0], v[1], v[-1]
    inferred = sum(v[2:-1])
    return (m, i, inferred, total) if _close(m + i + inferred, total) else None


def _mark_total(block: _Block) -> bool:
    """Find the block's total row and check its bands add up to it. False = drop the block."""
    rows = block.rows
    if len(set(r.depth_range for r in rows)) != len(rows):
        return False
    if len(rows) == 1:
        rows[0].is_total = rows[0].depth_range == "0-1200"
        return True
    last, bands = rows[-1], rows[:-1]
    start, end = min(r.span[0] for r in bands), max(r.span[1] for r in bands)
    if last.span != (start, end):
        return True  # no total row printed: every row is a band
    if all(
        _close(sum(getattr(r, k) for r in bands), getattr(last, k))
        for k in ("measured", "indicated", "inferred")
    ):
        last.is_total = True
        return True
    # A "0-600" after 0-300 and 300-600 that doesn't add up is not a band either (Jharia's
    # 0-600 band comes before the 300-600 row); the printed numbers disagree, so drop it all.
    return False


def _start(prefix: str, section: str | None, state: str | None) -> tuple[_Block | None, str | None]:
    """A labelled line starts a block: (the block, or None to skip its rows; current state)."""
    if GRAND.match(prefix):
        return _Block(None, None, None), None  # all India: both sections together
    if m := TOTAL_FOR.match(prefix):
        found = state_of(m.group(1))
        if found is None:
            log.warning("Depth table: unknown state %r, block skipped", m.group(1))
            return None, None
        return _Block(section, found, None), found
    t = COAL_TYPE.search(prefix)
    if t is None:
        log.warning("Depth table: no coal type in %r, block skipped", prefix)
        return None, state
    if rest := prefix[: t.start()].strip():
        state = state_of(rest)
        if state is None:
            log.warning("Depth table: unknown state %r, block skipped", rest)
    if state is None:
        return None, None
    return _Block(section, state, re.sub(r"\s+", " ", t.group(1)).upper()), state


def rows_from_lines(lines: list[Line]) -> list[DepthRow]:
    """The table's rows, from the printed lines of its pages (pure; tested without a PDF)."""
    blocks: list[_Block] = []
    section: str | None = None
    state: str | None = None
    block: _Block | None = None
    k = 0
    while k < len(lines):
        line = lines[k]
        k += 1
        words = line.words
        if len(words) == 1 and words[0].upper() in SECTIONS:
            section, state, block = words[0].upper(), None, None
            continue
        at = next((j for j, w in enumerate(words) if DEPTH.match(w)), None)
        if at is None:
            continue  # headers, notes, page numbers, the unlabelled grand-total line
        numbers = [w for w in words[at + 1 :] if NUMBER.match(w)]
        # A total that wrapped onto its own line ("0-600* 15229.16 153.93 29.63 0.00" then
        # "15412.72"): take it when the row doesn't add up without it.
        if _values(numbers) is None and k < len(lines):
            nxt = lines[k].words
            if len(nxt) == 1 and DECIMAL.match(nxt[0]) and _values([*numbers, nxt[0]]):
                numbers.append(nxt[0])
                k += 1
        prefix = " ".join(words[:at]).strip()
        if prefix:
            block, state = _start(prefix, section, state)
            if block is not None:
                blocks.append(block)
        if block is None:
            continue
        values = _values(numbers)
        if values is None:
            log.warning("Depth table p.%d: row does not add up, skipped: %s", line.page_no, words)
            continue
        m_, i_, inf_, t_ = values
        a, b = DEPTH.match(words[at]).groups()
        block.rows.append(
            DepthRow(
                page_no=line.page_no,
                bbox=line.bbox,
                section=block.section,
                state=block.state,
                coal_type=block.coal_type,
                depth_range=f"{int(a)}-{int(b)}",
                values_raw=numbers,
                measured=m_,
                indicated=i_,
                inferred=inf_,
                total=t_,
            )
        )

    out: list[DepthRow] = []
    for b in blocks:
        if not b.rows:
            continue
        if _mark_total(b):
            out.extend(b.rows)
        else:
            log.warning(
                "Depth table: %s %s bands don't add up, block skipped", b.state, b.coal_type
            )
    return out


def period_of(text: str) -> str | None:
    """ "(As on 01.04.2025)" -> "2025-04", like the facts extractor stores "as on" figures."""
    m = AS_ON.search(text)
    return f"{m.group(3)}-{int(m.group(2)):02d}" if m else None


def _page_lines(page, page_no: int) -> list[Line]:
    """Words grouped into printed lines by their vertical centre, left to right."""
    rows: dict[int, list] = {}
    for w in page.get_text("words"):
        rows.setdefault(round((w[1] + w[3]) / 2 / 3), []).append(w)
    lines = []
    for key in sorted(rows):
        ws = sorted(rows[key], key=lambda w: w[0])
        box = [
            min(w[0] for w in ws),
            min(w[1] for w in ws),
            max(w[2] for w in ws),
            max(w[3] for w in ws),
        ]
        lines.append(Line([w[4] for w in ws], [round(x, 1) for x in box], page_no))
    return lines


def read_pdf(path: Path) -> tuple[str | None, list[DepthRow]]:
    """(period, rows) of the depth table in a PDF; (None, []) when it has none."""
    import pymupdf

    period = None
    lines: list[Line] = []
    with pymupdf.open(path) as pdf:
        active = False
        for page in pdf:
            text = page.get_text()
            if TITLE.search(text):
                active = True
                period = period_of(text) or period
            elif active and not re.search(r"\bState\s+Coal\s+Type\b", text):
                active = False  # the table's pages repeat its column header; this one doesn't
            if active:
                lines.extend(_page_lines(page, page.number + 1))
    if not lines or period is None:
        return None, []
    return period, rows_from_lines(lines)


def extract_depth(db: Session, doc: Document) -> int:
    """Replace a document's depth rows with those read from its PDF. Returns the row count."""
    db.execute(delete(DepthResource).where(DepthResource.document_id == doc.id))
    if doc.mime_type != "application/pdf" or not Path(doc.file_path).exists():
        return 0
    period, rows = read_pdf(Path(doc.file_path))
    for r in rows:
        db.add(
            DepthResource(
                document_id=doc.id,
                page_no=r.page_no,
                bbox=r.bbox,
                period=period,
                section=r.section,
                state=r.state,
                coal_type=r.coal_type,
                depth_range=r.depth_range,
                is_total=r.is_total,
                measured=r.measured,
                indicated=r.indicated,
                inferred=r.inferred,
                total=r.total,
                values_raw=r.values_raw,
            )
        )
    if rows:
        log.info("Document %s: %d depth-wise resource rows (%s)", doc.id, len(rows), period)
    return len(rows)


def extract_depth_document(document_id: str) -> int:
    """Worker job / CLI: (re)read the depth table of an already processed document. Leaves its
    facts and any review decisions alone."""
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        doc = db.get(Document, uuid.UUID(document_id))
        if doc is None:
            raise ValueError(f"{document_id}: no such document")
        n = extract_depth(db, doc)
        db.commit()
        return n


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    for arg in sys.argv[1:]:
        print(f"{arg}: {extract_depth_document(arg)} depth rows")
