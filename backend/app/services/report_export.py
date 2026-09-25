"""DOCX and PDF export of a report: the official PQ-reply layout, the monthly report and the
briefing note (guide 10.1).

The layout itself (Ministry header, house, Starred/Unstarred Question No., date, subject, MP
and the parts, ANSWER, Minister line placeholder, Statement for starred questions, answers,
Annexures, internal Sources list) is built once in pq_reply.layout as lines and tables; this
module only draws those items.

DOCX is built with python-docx and PDF with PyMuPDF's Story (HTML -> PDF), both already
dependencies, so no LibreOffice or new package is needed. PyMuPDF shapes Devanagari, so Hindi
replies render correctly. A report that is not APPROVED carries a "DRAFT" line, its warnings
and a note under each part where unsupported figures were removed.

Two sources of content: a generated reply (blocks in content_json), or a reply edited in the
plain-text editor, which saves only {text}. That text is already the full reply (render_text
output, edited), so it is drawn as it is; the header and sources are only added when the text
does not have them.

Monthly reports and briefing notes (report_builder.layout) use the same items plus
("chart", {...}): a bar chart drawn with PyMuPDF into a PNG, inserted as a picture in the DOCX
and as an image in the PDF. PyMuPDF is already a dependency, so no Matplotlib (≈40 MB with its
font cache) is needed for these simple grouped bar charts.
"""

from __future__ import annotations

import html
import io
import math
import re

import pymupdf
from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from app.services import report_builder
from app.services.pq_reply import (
    DRAFT_LINE,
    SOURCES_HEADING,
    header_lines,
    layout,
)

_MARK = re.compile(r"(\[S\d+\])")
_CENTRED = re.compile(r"^(ANSWER|STATEMENT|ANNEXURE-[IVXL]+|THE MINISTER OF .*)$")
_CAPTION = re.compile(r"^(Statement referred to|Referred to) in reply to ")
_ASKER = re.compile(r"^[\w*/-]+\. [^a-z]+:$")  # "1234. SHRI A. B. MEMBER:"

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"


def is_approved(report) -> bool:
    return report.status.value in ("APPROVED", "EXPORTED")


def items_from_text(
    text: str, *, header: dict | None, sources: list[dict], title: str, approved: bool
) -> list[tuple]:
    """Layout items for a reply edited as plain text. Lines up to the first blank line are the
    header when the text starts with it; "a | b" line runs become tables."""
    items: list[tuple] = []
    if not approved:
        items.append(("line", DRAFT_LINE, "note"))
    lines = text.strip("\n").splitlines()
    has_header = bool(lines) and lines[0].strip() == "GOVERNMENT OF INDIA"
    if not has_header:
        if header:
            items += [("line", h, "title") for h in header_lines(header)] + [("line", "", "normal")]
        else:
            items.append(("line", title, "title"))
    in_header, in_sources, table_rows = has_header, False, []

    def flush_table() -> None:
        if table_rows:
            items.append(("table", {"columns": table_rows[0], "rows": table_rows[1:]}))
            table_rows.clear()

    subject_next = False
    for raw in lines:
        line = raw.strip()
        if " | " in line and not in_sources:
            table_rows.append([c.strip() for c in line.split(" | ")])
            continue
        flush_table()
        if not line:
            subject_next = in_header  # render_text puts the subject after the header block
            in_header = False
            items.append(("line", "", "normal"))
            continue
        if line == SOURCES_HEADING:
            in_sources = True
            items.append(("line", line, "bold"))
        elif in_sources:
            items.append(("line", line, "small"))
        elif in_header or subject_next or _CENTRED.match(line):
            items.append(("line", line, "title"))
        elif _CAPTION.match(line):
            items.append(("line", line, "caption"))
        elif _ASKER.match(line):
            items.append(("line", line, "bold"))
        else:
            items.append(("line", line, "normal"))
        subject_next = False
    flush_table()
    if sources and SOURCES_HEADING not in text:
        items += [("line", "", "normal"), ("line", SOURCES_HEADING, "bold")]
        items += [
            ("line", f"[{s['id']}] {s['document']}, page {s['page']}", "small") for s in sources
        ]
    return items


DRAFT_KINDS = ("monthly", "briefing")


def items_for_report(report, pq_header: dict | None, db_sources: list[dict]) -> list[tuple]:
    content = report.content_json or {}
    approved = is_approved(report)
    kind = getattr(getattr(report, "report_type", None), "value", None) or content.get("kind")
    if content.get("kind") in DRAFT_KINDS or kind in DRAFT_KINDS:
        if content.get("sections") and content.get("title"):
            return report_builder.layout(content, internal_notes=not approved)
        return report_builder.items_from_text(
            content.get("text", ""), sources=db_sources, title=report.title, approved=approved
        )
    blocks = content.get("blocks") or []
    header = content.get("header") or pq_header
    if blocks and header:
        return layout(
            header,
            blocks,
            content.get("sources") or db_sources,
            internal_notes=not approved,
            warnings=content.get("warnings") or [],
        )
    return items_from_text(
        content.get("text", ""),
        header=pq_header,
        sources=db_sources,
        title=report.title,
        approved=approved,
    )


# --- DOCX ---------------------------------------------------------------------------------------


def _para(doc, text: str, style: str):
    p = doc.add_paragraph()
    if style in ("title", "caption"):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pieces = [text] if style == "small" else _MARK.split(text)
    for piece in pieces:
        if not piece:
            continue
        run = p.add_run(piece)
        run.bold = style in ("title", "bold")
        if style != "small" and _MARK.fullmatch(piece):  # source markers: like footnote numbers
            run.font.superscript = True
            run.font.size = Pt(8)
        elif style in ("caption", "note"):
            run.font.size = Pt(9.5)
        elif style == "small":
            run.font.size = Pt(9)
        if style == "note":
            run.font.color.rgb = RGBColor(0xB0, 0x00, 0x00)
    return p


def _docx_table(doc, table: dict) -> None:
    width = max([len(table["columns"])] + [len(r) for r in table["rows"]])
    t = doc.add_table(rows=1, cols=width)
    t.style = "Table Grid"
    for cell, text in zip(t.rows[0].cells, table["columns"], strict=False):
        cell.text = ""
        cell.paragraphs[0].add_run(str(text)).bold = True
    for row in table["rows"]:
        for cell, text in zip(t.add_row().cells, row, strict=False):
            cell.text = str(text)
    doc.add_paragraph()


# --- charts -------------------------------------------------------------------------------------

# Categorical slots 1-3 of the dataviz reference palette (blue, orange, aqua), checked for
# colour-blind separation; the legend names every series, and the table above the chart
# holds the same figures, so colour never carries meaning alone.
_SERIES_RGB = [(0x2A, 0x78, 0xD6), (0xEB, 0x68, 0x34), (0x1B, 0xAF, 0x7A), (0xED, 0xA1, 0x00)]
_INK = (0x52 / 255, 0x51 / 255, 0x4E / 255)
_GRID = (0.88, 0.88, 0.86)


def axis_ticks(value: float) -> list[float]:
    """0 up to at least `value` in 3-5 even steps of 1, 2 or 5 x 10^n (0, 5, 10, 15, 20, 25)."""
    if value <= 0:
        return [0.0, 1.0]
    exp = 10 ** math.floor(math.log10(value))
    step = next(m * e for e in (exp / 10, exp) for m in (1, 2, 5) if value / (m * e) <= 5)
    n = math.ceil(value / step - 1e-9)
    return [round(i * step, 10) for i in range(n + 1)]


def chart_png(chart: dict, width: float = 480, height: float = 230, dpi: int = 150) -> bytes:
    """A grouped bar chart as PNG: one group per label, one bar per series, a light grid and
    a legend. Missing values ("–") are simply left out, never drawn as zero."""
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    left, right, top, bottom = 44, width - 10, 30, height - 34
    labels, series = chart["labels"], chart["series"][: len(_SERIES_RGB)]
    values = [v for s in series for v in s["values"] if v is not None]
    ticks = axis_ticks(max(values, default=0))
    top_value = ticks[-1]
    title = re.sub(r"^\d+\.\s*", "", chart.get("title", "")).capitalize()
    page.insert_text((left, 14), f"{title} ({chart.get('unit', '')})"[:90],
                     fontsize=9, color=(0.04, 0.04, 0.04))  # fmt: skip
    for tick in ticks:  # grid + y labels
        y = bottom - (bottom - top) * tick / top_value
        page.draw_line((left, y), (right, y), color=_GRID, width=0.5)
        label = f"{tick:g}"
        page.insert_text((left - 6 - 4.2 * len(label), y + 3), label, fontsize=7, color=_INK)
    group = (right - left) / max(len(labels), 1)
    bar = min(18.0, (group * 0.75) / max(len(series), 1))
    for gi, label in enumerate(labels):
        x0 = left + gi * group + (group - bar * len(series)) / 2
        for si, s in enumerate(series):
            v = s["values"][gi] if gi < len(s["values"]) else None
            if v is None:
                continue
            h = (bottom - top) * max(v, 0) / top_value
            rect = pymupdf.Rect(x0 + si * bar + 1, bottom - h, x0 + (si + 1) * bar - 1, bottom)
            color = tuple(c / 255 for c in _SERIES_RGB[si])
            page.draw_rect(rect, color=None, fill=color, width=0)
        text = label.split("/")[0]  # "Captive/Others" -> "Captive"
        text = text if len(text) <= 9 else text[:8] + "."
        page.insert_text((left + gi * group + group / 2 - 2.1 * len(text), bottom + 10), text,
                         fontsize=7, color=_INK)  # fmt: skip
    page.draw_line((left, bottom), (right, bottom), color=_INK, width=0.6)
    x = left
    for si, s in enumerate(series):  # legend
        color = tuple(c / 255 for c in _SERIES_RGB[si])
        page.draw_rect(pymupdf.Rect(x, height - 14, x + 8, height - 6), color=None, fill=color)
        page.insert_text((x + 11, height - 7), s["name"], fontsize=7.5, color=_INK)
        x += 18 + 4.4 * len(s["name"])
    png = page.get_pixmap(dpi=dpi).tobytes("png")
    doc.close()
    return png


def to_docx(items: list[tuple]) -> bytes:
    doc = DocxDocument()
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(11)
    for item in items:
        if item[0] == "line":
            _para(doc, item[1], item[2])
        elif item[0] == "table":
            _docx_table(doc, item[1])
        elif item[0] == "chart":
            doc.add_picture(io.BytesIO(chart_png(item[1])), width=Inches(6))
        else:
            doc.add_page_break()
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --- PDF ----------------------------------------------------------------------------------------

_CSS = """
body { font-family: sans-serif; font-size: 11pt; }
p { margin: 0 0 5pt 0; }
.title { text-align: center; font-weight: bold; }
.bold { font-weight: bold; }
.caption { text-align: center; font-size: 10pt; }
.note { color: #b00000; font-size: 9pt; }
.small { font-size: 9pt; margin: 0; }
sup { font-size: 7pt; }
table { border-collapse: collapse; margin: 4pt 0 8pt 0; }
td, th { border: 1px solid #000; padding: 2pt 4pt; font-size: 9.5pt; }
"""


def _html_table(table: dict) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in table["columns"])
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>"
        for row in table["rows"]
    )
    return f"<table><tr>{head}</tr>{body}</table>"


def to_html(items: list[tuple], archive: pymupdf.Archive | None = None) -> str:
    """HTML for the PDF Story; chart PNGs are added to `archive` and referenced by name."""
    out: list[str] = []
    for n, item in enumerate(items):
        if item[0] == "line":
            text, style = item[1], item[2]
            body = html.escape(text)
            if style != "small":
                body = _MARK.sub(lambda m: f"<sup>{m.group(1)}</sup>", body)
            out.append(f'<p class="{style}">{body or "&#160;"}</p>')
        elif item[0] == "table":
            out.append(_html_table(item[1]))
        elif item[0] == "chart":
            if archive is not None:
                name = f"chart{n}.png"
                archive.add((chart_png(item[1]), name))
                out.append(f'<p><img src="{name}" width="440"/></p>')
        else:
            out.append("<br/>")
    return "<body>" + "".join(out) + "</body>"


def to_pdf(items: list[tuple]) -> bytes:
    archive = pymupdf.Archive()
    story = pymupdf.Story(html=to_html(items, archive), user_css=_CSS, archive=archive)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    page = pymupdf.paper_rect("a4")
    area = page + (60, 56, -60, -56)
    more = True
    while more:
        device = writer.begin_page(page)
        more, _ = story.place(area)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buf.getvalue()
