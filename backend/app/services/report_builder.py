"""Shared parts of the monthly report and the briefing note (guide 10.1, W5 and W6).

Both drafts are a title, a few sections (heading, lines or bullets, an optional table) and a
sources list. This module holds what they share:

- `FactRow` and `fetch_facts`: the one facts query, org-scoped through the fact's document
  (a user sees facts from their unit's documents and from public documents, like every other
  query). It reads only metric, subsidiary, period (+ its type: a YTD fact has the same
  "2024-12" period text as the month), status, value_std, document and page.
- `DocSources`: numbers sources S1, S2… by document page. Several facts from the same page
  share one number; every fact / chunk used is still its own `report_citations` row, and the
  row's location ends with ":S<n>" so the list can be rebuilt after a plain-text edit.
- `layout`: sections -> the same ("line" | "table" | "chart" | "pagebreak") items the PQ reply
  uses, so the editor text, DOCX and PDF come from one place (report_export draws them).
- `chart_for_table`: the chart under a table is drawn from the table itself, so a draft edited
  in the plain-text editor still gets the chart that matches its (edited) figures.
- `items_from_text`: layout items for a draft saved by the plain-text editor.

Everything here except `fetch_facts` is pure.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select

from app.core.deps import scope_to_user
from app.models import Document, Fact
from app.models.enums import FactStatus
from app.services.normalise import parse_number
from app.services.pq_reply import DRAFT_LINE, items_to_text, removed_note

SOURCES_HEADING = "SOURCES"
NOT_FOUND_CELL = "–"  # a figure not found in the available documents; never a guess
UNVERIFIED_MARK = "*"
UNVERIFIED_NOTE = (
    "* Not yet verified by a Reviewer (extracted automatically from the source document)."
)
NOT_FOUND_NOTE = "– Not found in the available documents."
COMPUTED_NOTE = (
    "Achievement and growth % are computed from the figures shown; the source document may "
    "show slightly different % worked out from unrounded figures."
)
TOTAL_LABELS = {"CIL", "All India"}  # left out of charts: they dwarf the subsidiaries
_MARK = re.compile(r"\[S\d+\]")


# --- facts ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FactRow:
    id: uuid.UUID
    metric: str
    subsidiary: str | None
    period: str | None
    status: str
    value_std: float | None
    confidence: float
    document_id: uuid.UUID
    document: str
    page: int
    period_type: str | None = None  # MONTH / FY (YTD and AS_ON share the same period text)

    @property
    def verified(self) -> bool:
        return self.status == FactStatus.VERIFIED.value


def fetch_facts(
    db,
    user,
    *,
    metrics: list[str],
    subsidiaries: list[str] | None = None,
    periods: list[str] | None = None,
    limit: int = 5000,
) -> list[FactRow]:
    """Facts the user may see, REJECTED ones left out (FLAGGED / EXTRACTED are kept and
    labelled unverified by the caller)."""
    stmt = (
        select(
            Fact.id,
            Fact.metric,
            Fact.subsidiary,
            Fact.period,
            Fact.status,
            Fact.value_std,
            Fact.confidence,
            Fact.document_id,
            Document.title,
            Fact.page_no,
            Fact.period_type,
        )
        .join(Document, Document.id == Fact.document_id)
        .where(Fact.metric.in_(metrics), Fact.status != FactStatus.REJECTED)
    )
    if subsidiaries:
        stmt = stmt.where(Fact.subsidiary.in_(subsidiaries))
    if periods:
        stmt = stmt.where(Fact.period.in_(periods))
    stmt = scope_to_user(stmt, Document, user).limit(limit)
    return [
        FactRow(
            id=r[0],
            metric=getattr(r[1], "value", r[1]),
            subsidiary=r[2],
            period=r[3],
            status=getattr(r[4], "value", r[4]),
            value_std=None if r[5] is None else float(r[5]),
            confidence=float(r[6] or 0),
            document_id=r[7],
            document=r[8],
            page=r[9],
            period_type=getattr(r[10], "value", r[10]),
        )
        for r in db.execute(stmt).all()
    ]


def best_fact(candidates: list[FactRow]) -> tuple[FactRow | None, bool]:
    """The fact to show for one table cell, and whether other usable facts disagree with it
    by more than 0.5% (guide rule V02). VERIFIED wins, then the higher extraction confidence,
    then the earliest page (the summary table usually comes first), so the choice is stable.
    REJECTED facts and facts whose unit could not be converted (no value_std) are ignored."""
    usable = [f for f in candidates if f.status != "REJECTED" and f.value_std is not None]
    if not usable:
        return None, False
    usable.sort(key=lambda f: (not f.verified, -f.confidence, f.document, f.page, str(f.id)))
    best = usable[0]
    conflict = any(
        abs(f.value_std - best.value_std) > 0.005 * max(abs(best.value_std), 1e-9)
        for f in usable[1:]
    )
    return best, conflict


def fmt_value(value: float | None, digits: int = 2) -> str:
    return NOT_FOUND_CELL if value is None else f"{value:.{digits}f}"


# --- sources -------------------------------------------------------------------------------------


@dataclass
class DocSources:
    """S1, S2… one per document page; each fact / chunk behind it is remembered for the
    report_citations rows."""

    sources: list[dict] = field(default_factory=list)
    _index: dict[tuple[str, int], str] = field(default_factory=dict)
    _links: dict[tuple[str, str, str], dict] = field(default_factory=dict)

    def add(
        self,
        *,
        document_id,
        document: str,
        page: int,
        where: str,
        fact_id=None,
        chunk_id=None,
    ) -> str:
        key = (str(document_id), int(page))
        if key not in self._index:
            sid = f"S{len(self.sources) + 1}"
            self._index[key] = sid
            self.sources.append(
                {
                    "id": sid,
                    "document_id": str(document_id),
                    "document": document,
                    "page": int(page),
                }
            )
        sid = self._index[key]
        source = str(fact_id or chunk_id or "")
        if source:
            link_key = (where, source, sid)
            self._links.setdefault(
                link_key,
                {
                    "fact_id": uuid.UUID(str(fact_id)) if fact_id else None,
                    "chunk_id": uuid.UUID(str(chunk_id)) if chunk_id and not fact_id else None,
                    "location_in_report": f"{where}:{sid}"[-200:],
                },
            )
        return sid

    def add_fact(self, fact: FactRow, where: str) -> str:
        return self.add(
            document_id=fact.document_id,
            document=fact.document,
            page=fact.page,
            where=where,
            fact_id=fact.id,
        )

    def links(self) -> list[dict]:
        return list(self._links.values())


def markers(sids) -> str:
    return "".join(f"[{s}]" for s in dict.fromkeys(sids))


# --- charts --------------------------------------------------------------------------------------


def _cell_number(cell: object) -> float | None:
    text = str(cell).replace(UNVERIFIED_MARK, "").strip()
    return None if text in ("", NOT_FOUND_CELL, "-") else parse_number(text)


def chart_for_table(table: dict, title: str = "") -> dict | None:
    """A bar chart of the table's quantity columns (those ending "(MT)" or "(Mcum)"):
    subsidiary tables leave out CIL / All India, period tables chart every period. None when
    there is nothing to draw, e.g. every figure is "–"."""
    columns = [str(c) for c in table.get("columns", [])]
    if not columns or columns[0] not in ("Subsidiary", "Period"):
        return None
    unit_cols = [i for i, c in enumerate(columns) if re.search(r"\((MT|Mcum)\)$", c)]
    rows = [r for r in table.get("rows", []) if r and str(r[0]) not in TOTAL_LABELS]
    if not unit_cols or not rows:
        return None
    series = []
    for i in unit_cols:
        values = [_cell_number(r[i]) if i < len(r) else None for r in rows]
        if any(v is not None for v in values):
            series.append({"name": re.sub(r"\s*\((MT|Mcum)\)$", "", columns[i]), "values": values})
    if not series:
        return None
    unit = re.search(r"\((MT|Mcum)\)$", columns[unit_cols[0]]).group(1)
    return {
        "title": title,
        "unit": unit,
        "labels": [str(r[0]) for r in rows],
        "series": series,
    }


# --- layout --------------------------------------------------------------------------------------


def section(
    sid: str,
    heading: str | None,
    lines: list[str] | None = None,
    *,
    bullets: bool = False,
    table: dict | None = None,
    notes: list[str] | None = None,
    removed_numbers: list[str] | None = None,
) -> dict:
    return {
        "id": sid,
        "heading": heading,
        "lines": list(lines or []),
        "bullets": bullets,
        "table": table,
        "notes": list(notes or []),  # printed under the table, part of the report
        "removed_numbers": list(removed_numbers or []),  # internal: drafts only
    }


def source_line(s: dict) -> str:
    return f"[{s['id']}] {s['document']}, page {s['page']}"


def layout(content: dict, *, internal_notes: bool) -> list[tuple]:
    """Title, subtitle, sections, sources. `internal_notes` adds the DRAFT line, warnings and
    removed-figure notes (unapproved exports only; never in the editor text)."""
    items: list[tuple] = []

    def line(text: str = "", style: str = "normal") -> None:
        items.append(("line", text, style))

    if internal_notes:
        line(DRAFT_LINE, "note")
        for w in content.get("warnings") or []:
            line(w, "note")
    line(content["title"], "title")
    if content.get("subtitle"):
        line(content["subtitle"], "title")
    line()
    for s in content.get("sections") or []:
        if s.get("heading"):
            line(s["heading"], "bold")
        for text in s.get("lines") or []:
            line(f"• {text}" if s.get("bullets") else text)
        if internal_notes and s.get("removed_numbers"):
            line(removed_note(s["removed_numbers"]), "note")
        if s.get("table"):
            items.append(("table", s["table"]))
            chart = chart_for_table(s["table"], s.get("heading") or "")
            if chart:
                items.append(("chart", chart))
        for note in s.get("notes") or []:
            line(note, "small")
        line()
    sources = content.get("sources") or []
    if sources:
        line(SOURCES_HEADING, "bold")
        for s in sources:
            line(source_line(s), "small")
    return items


def render_text(content: dict) -> str:
    """Plain rendering for the plain-text report editor (charts are redrawn from the tables
    on export, so they need no text)."""
    items = [i for i in layout(content, internal_notes=False) if i[0] != "chart"]
    return items_to_text(items)


def _is_heading(line: str) -> bool:
    """Section headings are upper case ("SUMMARY", "1. COAL PRODUCTION")."""
    letters = re.sub(r"[^A-Za-z]", "", line)
    return len(letters) >= 4 and letters.isupper() and not line.startswith("[")


def items_from_text(text: str, *, sources: list[dict], title: str, approved: bool) -> list[tuple]:
    """Layout items for a monthly report / briefing note saved as plain text: lines up to the
    first blank line are the title, upper-case lines are headings, "a | b" runs are tables
    (with their chart), and the sources list is added from report_citations when the text has
    none."""
    items: list[tuple] = []
    if not approved:
        items.append(("line", DRAFT_LINE, "note"))
    lines = text.strip("\n").splitlines()
    if not lines or not lines[0].strip():
        items.append(("line", title, "title"))
    in_title, in_sources, heading, table_rows = True, False, "", []

    def flush_table() -> None:
        if table_rows:
            table = {"columns": table_rows[0], "rows": table_rows[1:]}
            items.append(("table", table))
            chart = chart_for_table(table, heading)
            if chart:
                items.append(("chart", chart))
            table_rows.clear()

    for raw in lines:
        line = raw.strip()
        if " | " in line and not in_sources:
            table_rows.append([c.strip() for c in line.split(" | ")])
            continue
        flush_table()
        if not line:
            in_title = False
            items.append(("line", "", "normal"))
        elif in_title:
            items.append(("line", line, "title"))
        elif line == SOURCES_HEADING:
            in_sources = True
            items.append(("line", line, "bold"))
        elif in_sources or line.startswith(("* ", "– ")):
            items.append(("line", line, "small"))
        elif _is_heading(line):
            heading = line
            items.append(("line", line, "bold"))
        else:
            items.append(("line", line, "normal"))
    flush_table()
    if sources and SOURCES_HEADING not in lines:
        items += [("line", "", "normal"), ("line", SOURCES_HEADING, "bold")]
        items += [("line", source_line(s), "small") for s in sources]
    return items


def has_marker(text: str) -> bool:
    return bool(_MARK.search(text))
