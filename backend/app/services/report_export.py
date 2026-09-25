"""DOCX and PDF export of a report in the official PQ-reply layout (guide 10.1).

Layout: Government of India / Ministry header · House · Starred/Unstarred Question No. · date ·
subject · MP and the question in parts · ANSWER · Minister line (placeholder) · the answer to
each part with small tables inline · Annexure tables · an internal Sources list giving the
document and page of every figure.

DOCX is built with python-docx and PDF with PyMuPDF's Story (HTML -> PDF), both already
dependencies, so no LibreOffice or new package is needed. PyMuPDF shapes Devanagari, so Hindi
replies render correctly. A report that is not APPROVED carries a "DRAFT" line on top.

The layout works from an ExportView, so the same code renders a generated reply (blocks) and a
reply that was edited in the plain-text editor (text only).
"""

from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass, field

import pymupdf
from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from app.services.pq_reply import (
    annexure_caption,
    part_prefix,
    question_heading,
)

DRAFT_LINE = "DRAFT - for internal review. Not approved; not to be sent."
SOURCES_HEADING = "SOURCES (internal, remove before sending)"
_MARK = re.compile(r"(\[S\d+\])")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"


@dataclass
class ExportView:
    title: str
    approved: bool
    header: dict | None  # pq_reply.build_header(...) shape; None for non-PQ reports
    blocks: list[dict] = field(default_factory=list)
    text: str = ""  # used when there are no blocks
    sources: list[dict] = field(default_factory=list)  # {id, document, page}


def view_from_report(report, pq_header: dict | None, db_sources: list[dict]) -> ExportView:
    """Blocks from content_json when present (generated reply); otherwise the edited plain text
    with the header rebuilt from the linked ParliamentQuestion and the sources from the
    report_citations rows."""
    content = report.content_json or {}
    blocks = content.get("blocks") or []
    approved = report.status.value in ("APPROVED", "EXPORTED")
    if blocks:
        return ExportView(
            title=report.title,
            approved=approved,
            header=content.get("header") or pq_header,
            blocks=blocks,
            sources=content.get("sources") or db_sources,
        )
    return ExportView(
        title=report.title,
        approved=approved,
        header=pq_header,
        text=content.get("text", ""),
        sources=db_sources,
    )


def _header_lines(h: dict) -> list[str]:
    return [
        "GOVERNMENT OF INDIA",
        h["ministry"],
        h["house_label"],
        question_heading(h),
        f"TO BE ANSWERED ON {h['answer_date_text']}",
    ]


def _asker_line(h: dict) -> str:
    return f"{h['q_no'] or '____'}. {h['mp_name'].upper() or 'SHRI/SMT. ____'}:"


# --- DOCX ---------------------------------------------------------------------------------------


def _para(doc, text: str = "", *, bold=False, center=False, size=None, color=None):
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for piece in _MARK.split(text):
        if not piece:
            continue
        run = p.add_run(piece)
        run.bold = bold
        if _MARK.fullmatch(piece):  # source markers: small superscript, like footnote numbers
            run.font.superscript = True
            run.font.size = Pt(8)
        elif size:
            run.font.size = Pt(size)
        if color:
            run.font.color.rgb = RGBColor(*color)
    return p


def _docx_table(doc, table: dict) -> None:
    t = doc.add_table(rows=1, cols=len(table["columns"]))
    t.style = "Table Grid"
    for cell, text in zip(t.rows[0].cells, table["columns"], strict=False):
        cell.text = ""
        cell.paragraphs[0].add_run(str(text)).bold = True
    for row in table["rows"]:
        cells = t.add_row().cells
        for cell, text in zip(cells, row, strict=False):
            cell.text = str(text)
    doc.add_paragraph()


def to_docx(view: ExportView) -> bytes:
    doc = DocxDocument()
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(11)
    if not view.approved:
        _para(doc, DRAFT_LINE, bold=True, center=True, size=9, color=(0xB0, 0x00, 0x00))

    h = view.header
    if h:
        for line in _header_lines(h):
            _para(doc, line, bold=True, center=True)
        _para(doc)
        _para(doc, h["subject"].upper(), bold=True, center=True)
        _para(doc)
        _para(doc, _asker_line(h), bold=True)
        _para(doc, h["intro"])
    else:
        _para(doc, view.title, bold=True, center=True, size=14)

    if view.blocks:
        for b in view.blocks:
            _para(doc, f"{part_prefix(b['part'])}{b['question']}")
        _para(doc)
        _para(doc, "ANSWER", bold=True, center=True)
        _para(doc, h["minister_line"] if h else "", bold=True, center=True)
        _para(doc)
        for b in view.blocks:
            prefix = f"({b['part']}): " if b["part"] else ""
            _para(doc, f"{prefix}{b['text']}")
            if b.get("table") and not b.get("annexure"):
                _docx_table(doc, b["table"])
        for b in view.blocks:
            if b.get("annexure"):
                doc.add_page_break()
                _para(doc, b["annexure"].upper(), bold=True, center=True)
                if h:
                    _para(doc, annexure_caption(h, b["part"]), center=True, size=10)
                _para(doc)
                _docx_table(doc, b["table"])
    else:
        for line in view.text.splitlines():
            _para(doc, line)

    if view.sources:
        _para(doc)
        _para(doc, SOURCES_HEADING, bold=True, size=10)
        for s in view.sources:
            _para(doc, f"{s['id']}  {s['document']}, page {s['page']}", size=9)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --- PDF ----------------------------------------------------------------------------------------

_CSS = """
body { font-family: sans-serif; font-size: 11pt; }
p { margin: 0 0 5pt 0; }
.c { text-align: center; font-weight: bold; }
.draft { text-align: center; color: #b00000; font-size: 9pt; font-weight: bold; }
.cap { text-align: center; font-size: 10pt; }
.src { font-size: 9pt; margin: 0; }
sup { font-size: 7pt; }
table { border-collapse: collapse; margin: 4pt 0 8pt 0; }
td, th { border: 1px solid #000; padding: 2pt 4pt; font-size: 9.5pt; }
"""


def _h(text: str) -> str:
    """Escape, and show [S1] markers as superscripts."""
    return _MARK.sub(lambda m: f"<sup>{m.group(1)}</sup>", html.escape(text))


def _html_table(table: dict) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in table["columns"])
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>"
        for row in table["rows"]
    )
    return f"<table><tr>{head}</tr>{body}</table>"


def to_html(view: ExportView) -> str:
    out: list[str] = []
    if not view.approved:
        out.append(f'<p class="draft">{html.escape(DRAFT_LINE)}</p>')
    h = view.header
    if h:
        out += [f'<p class="c">{html.escape(line)}</p>' for line in _header_lines(h)]
        out.append(f'<p class="c"><br/>{html.escape(h["subject"].upper())}</p><br/>')
        out.append(f"<p><b>{html.escape(_asker_line(h))}</b></p>")
        out.append(f"<p>{html.escape(h['intro'])}</p>")
    else:
        out.append(f'<p class="c">{html.escape(view.title)}</p>')
    annexures: list[str] = []
    if view.blocks:
        out += [f"<p>{_h(part_prefix(b['part']) + b['question'])}</p>" for b in view.blocks]
        out.append('<br/><p class="c">ANSWER</p>')
        if h:
            out.append(f'<p class="c">{html.escape(h["minister_line"])}</p><br/>')
        for b in view.blocks:
            prefix = f"({b['part']}): " if b["part"] else ""
            out.append(f"<p>{_h(prefix + b['text'])}</p>")
            if b.get("table") and not b.get("annexure"):
                out.append(_html_table(b["table"]))
            elif b.get("annexure"):
                caption = annexure_caption(h, b["part"]) if h else ""
                annexures.append(
                    f'<p class="c">{html.escape(b["annexure"].upper())}</p>'
                    f'<p class="cap">{html.escape(caption)}</p>{_html_table(b["table"])}'
                )
    else:
        out += [f"<p>{_h(line) or '&#160;'}</p>" for line in view.text.splitlines()]
    out += annexures
    if view.sources:
        out.append(f"<br/><p><b>{html.escape(SOURCES_HEADING)}</b></p>")
        for s in view.sources:
            line = f"{s['id']}  {s['document']}, page {s['page']}"
            out.append(f'<p class="src">{html.escape(line)}</p>')
    return "<body>" + "".join(out) + "</body>"


def to_pdf(view: ExportView) -> bytes:
    story = pymupdf.Story(html=to_html(view), user_css=_CSS)
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
