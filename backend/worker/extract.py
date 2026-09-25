"""Tables -> facts (guide 7.2-7.4).

Rules first: headers and row labels are mapped with keyword rules; every number is copied
from its cell by code, never retyped. Two layouts are supported today, both checked on real
documents:

1. Entity rows = CIL subsidiaries (ECL ... NEC, CIL, SCCL, Captives, Grand Total), columns =
   production / coking coal / despatch / target for a month, year-to-date or FY
   (Ministry "Monthly Coal Statistics").
2. Entity rows = states, columns = Measured / Indicated / Inferred / Total resource "as on" a
   date (CMPDI "National Coal Inventory", state-wise tables).

Any other table produces no facts (it stays searchable as text). Growth %, achievement % and
share columns are skipped: they are calculated, not source figures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import Metric, PeriodType
from app.services.normalise import (
    MONTHS,
    find_unit,
    month_in_fy,
    normalise_fy,
    parse_number,
    state_name,
    subsidiary_code,
    to_ascii_digits,
)
from worker.parse import BBox, Table

CONFIDENCE_THRESHOLD = 0.85  # guide 7.4: below this -> flagged for review


@dataclass
class FactDraft:
    metric: Metric
    value_raw: str
    value: float
    unit: str | None
    value_std: float
    period_type: PeriodType | None
    period: str | None
    confidence: float
    page_no: int
    bbox: BBox | None
    label: str  # "row label · column label", shown to the reviewer
    subsidiary: str | None = None
    state: str | None = None
    category: str | None = None
    unit_guessed: bool = False
    flags: list[str] = field(default_factory=list)

    def key(self) -> tuple:
        """Identity of the figure, used by the duplicate / conflict rules."""
        return (self.metric, self.subsidiary, self.state, self.category, self.period_type,
                self.period)  # fmt: skip


@dataclass
class Column:
    index: int
    label: str
    metric: Metric
    category: str | None
    period_type: PeriodType | None
    period: str | None
    mapping_confidence: float
    unit: tuple[str, str, float] | None


_SKIP_COLUMN = re.compile(r"%|growth|achmt|achievement|share|s\.?\s?no|sl\.?\s?no|sr\.?\s?no", re.I)
_SUB_ENTITY_HEADER = re.compile(r"\bmines?\b|area\s*/\s*block|\bblock\b|coalfield", re.I)
_FY_LABEL = re.compile(
    r"\bF\.?Y\.?\s*'?(\d{2}(?:\d{2})?)\b|\b(20\d{2})\s*[-–/]\s*(\d{2,4})\b", re.I
)
_MONTH = re.compile(r"\b(" + "|".join(MONTHS) + r")[a-z]*\.?(?:\s*'?\s*(\d{2,4}))?\b", re.I)
_UPTO = re.compile(r"\b(?:up\s*to|upto|till|cumulative|cum\.?)\b", re.I)
_AS_ON = re.compile(r"as\s+on\s+(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", re.I)
_COLUMN_NUMBERS = re.compile(r"^\d{1,2}$")
_DATE_IN_LABEL = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b")
_COKING = re.compile(r"(?<!non-)(?<!non )\bcoking\b", re.I)


def _last_line(cell: str) -> str:
    return cell.split("\n")[-1].strip()


def _is_numeric(cell: str) -> bool:
    return parse_number(_last_line(cell)) is not None


# --- table clean-up ------------------------------------------------------------------------------


def _split_stacked_rows(table: Table) -> Table:
    """One PDF row that holds two table rows ("JHARKHAND\\nCHHATTISGARH", "60290.47\\n45462.6")
    becomes two rows. Only when every filled cell splits into the same number of parts and
    the parts in number columns are all numbers, so a merged sub-header is never split."""
    rows, cells = [], []
    for r, row in enumerate(table.rows):
        parts = [c.split("\n") if c else [] for c in row]
        counts = {len(p) for p in parts if p}
        n = counts.pop() if len(counts) == 1 else 1
        numeric_ok = all(
            all(parse_number(x) is not None for x in p) for p in parts if p and _is_numeric(p[0])
        )
        has_numbers = any(p and parse_number(p[0]) is not None for p in parts)
        boxes = table.cells[r] if table.cells else [None] * len(row)
        if n > 1 and numeric_ok and has_numbers:
            for i in range(n):
                rows.append([p[i].strip() if p else "" for p in parts])
                cells.append([_slice_box(b, i, n) for b in boxes])
        else:
            rows.append(
                list(row)
            )  # a copy: header repair edits cells, the stored table must not change
            cells.append(boxes)
    return Table(rows, table.bbox, table.title, cells if table.cells else None)


def _slice_box(box: BBox | None, i: int, n: int) -> BBox | None:
    if box is None:
        return None
    h = (box[3] - box[1]) / n
    return [box[0], box[1] + i * h, box[2], box[1] + (i + 1) * h]


def _looks_like_header(cell: str) -> bool:
    first = cell.split("\n")[0]
    return bool(_SKIP_COLUMN.search(first) or _FY_LABEL.search(first))


def _header_and_data(table: Table) -> tuple[list[str], int]:
    """Column labels (spanning headers filled across, sub-headers joined with ' / ') and the
    index of the first data row. Sub-headers glued into the first data row ("FY 25\\n5.06") are
    split off and the cell is left with just its value."""
    rows = table.rows
    width = max(len(r) for r in rows)
    # A data row has 2+ numbers (1 is enough in a narrow label + value table); a row of column
    # numbers "1 | 2 | 3" is not data.
    needed = 1 if width <= 3 else 2
    first_data = next(
        (i for i, r in enumerate(rows) if i > 0 and sum(_is_numeric(c) for c in r) >= needed
         and not all(_COLUMN_NUMBERS.match(c.strip()) for c in r if c.strip())),
        len(rows),
    )  # fmt: skip
    labels = [""] * width
    for r in rows[:first_data]:
        if all(_COLUMN_NUMBERS.match(c.strip()) for c in r if c.strip()):
            continue  # "1 | 2 | 3 | ..." column-number row
        filled, last = [], ""
        for c in range(width):
            text = (r[c] if c < len(r) else "").replace("\n", " ").strip()
            last = text or (last if r is rows[0] else "")  # spanning group headers fill right
            filled.append(text or (last if r is rows[0] else ""))
        labels = [
            f"{a} / {b}".strip(" /") if b and b != a else a
            for a, b in zip(labels, filled, strict=True)
        ]

    if first_data < len(rows):
        data = rows[first_data]
        for c, cell in enumerate(data):
            parts = cell.split("\n")
            head = " ".join(p.strip() for p in parts[:-1]) if len(parts) > 1 else ""
            value = parts[-1].strip()
            if parse_number(value) is None and _looks_like_header(cell):
                head, value = cell.replace("\n", " "), ""  # "Achmt.(%)" / "Growth (%) ▲ 9.4"
            elif not head:
                continue  # an ordinary cell such as the row label "ECL"
            if head and parse_number(head) is None:
                labels[c] = f"{labels[c]} / {head}".strip(" /")
                data[c] = value
    return labels, first_data


# --- column meaning ----------------------------------------------------------------------------


def _fy_from_label(text: str) -> str | None:
    m = _FY_LABEL.search(text)
    if not m:
        return None
    try:
        return normalise_fy(f"FY{m.group(1)}" if m.group(1) else f"{m.group(2)}-{m.group(3)}")
    except ValueError:
        return None


def _map_column(
    index: int, label: str, context: str, doc_fy: str | None, table_month: int | None,
    table_fy: str | None, as_on: str | None, resource_table: bool, coal_type: str | None = None,
) -> Column | None:  # fmt: skip
    text = label.lower()
    if not label or _SKIP_COLUMN.search(label):
        return None
    ctx = context.lower()
    unit = find_unit(label)

    # What is measured
    category = None
    if resource_table:
        for name in ("measured", "indicated", "inferred", "total", "resource"):
            if name in text:
                category = "Total" if name in ("total", "resource") else name.capitalize()
                if name == "inferred" and ("explor" in text or "mapping" in text):
                    category += " (Exploration)" if "explor" in text else " (Mapping)"
                break
        if category is None:
            return None
        metric = Metric.COAL_RESOURCE
    elif "target" in text:
        if "despatch" in text or "despatch" in ctx or "dispatch" in ctx or "coking" in ctx:
            return None  # only a production target exists in the fixed metric list
        metric = Metric.PRODUCTION_TARGET
    elif re.search(r"despatch|dispatch|off-?take", text):
        metric = Metric.COAL_OFFTAKE
    elif re.search(r"\bprod", text):
        metric = (
            Metric.COKING_COAL_PRODUCTION
            if "coking" in ctx or "coking" in text
            else (Metric.COAL_PRODUCTION)
        )
    elif re.search(r"\bobr\b|overburden|over burden", text):
        metric = Metric.OB_REMOVAL
    else:
        return None

    # For which period
    if resource_table:
        if coal_type:
            category = f"{category} · {coal_type}"
        own_date = _DATE_IN_LABEL.search(
            label
        )  # "resource as on / 01.04.2024" beats the table date
        if own_date:
            d, m, y = (int(g) for g in own_date.groups())
            as_on = f"{y:04d}-{m:02d}-{d:02d}"
        period_type, period, conf = (PeriodType.AS_ON, as_on, 1.0) if as_on else (None, None, 0.5)
        return Column(index, label, metric, category, period_type, period, conf, unit)

    fy, conf = _fy_from_label(label), 1.0
    if fy is None:
        fy, conf = table_fy or doc_fy, 0.9
    month_match = _MONTH.search(label)
    month = MONTHS[month_match.group(1).lower()[:3]] if month_match else None
    if month is None and "monthly" in text:
        month = table_month
    if fy is None:
        return Column(index, label, metric, category, None, None, 0.5, unit)
    if month is not None:
        period_type = PeriodType.YTD if _UPTO.search(label) else PeriodType.MONTH
        return Column(index, label, metric, category, period_type, month_in_fy(month, fy), conf,
                      unit)  # fmt: skip
    if "annual" in text or re.fullmatch(r"(?:fy\s*)?\d{4}\s*[-–]\s*\d{2,4}", text.strip()):
        return Column(index, label, metric, category, PeriodType.FY, fy, conf, unit)
    return Column(index, label, metric, category, None, None, 0.5, unit)


# --- main entry ----------------------------------------------------------------------------------


def extract_facts(
    table: Table,
    page_no: int,
    context: str,
    doc_fy: str | None,
    cell_confidence: float = 1.0,
) -> list[FactDraft]:
    """Facts from one table. `context` = text around the table (title, "Fig. in MT", topic)."""
    if len(table.rows) < 2:
        return []
    table = _split_stacked_rows(table)
    labels, first_data = _header_and_data(table)
    header_text = " ".join(labels)
    if _SUB_ENTITY_HEADER.search(header_text):
        return []  # mine- / block-wise tables: rows are not subsidiaries or states

    context = to_ascii_digits(f"{table.title or ''} {context}")
    resource_table = bool(re.search(r"measured|indicated|inferred", header_text, re.I))
    # Resource of one coal type only (e.g. "Table-VA: COKING COAL"), not the overall figure
    coal_type = "Coking" if resource_table and _COKING.search(header_text) else None
    as_on = None
    if m := _AS_ON.search(f"{header_text} {context}"):
        as_on = f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    fys = [f for f in (_fy_from_label(label) for label in labels) if f]
    table_fy = max(fys) if fys else None
    months = [MONTHS[m.group(1).lower()[:3]] for m in (_MONTH.search(lb) for lb in labels) if m]
    table_month = months[0] if months else None
    table_unit = find_unit(header_text) or find_unit(context)

    columns = [
        col
        for i, label in enumerate(labels)
        if (col := _map_column(i, label, context, doc_fy, table_month, table_fy, as_on,
                               resource_table, coal_type))  # fmt: skip
    ]
    if not columns:
        return []

    facts: list[FactDraft] = []
    for r in range(first_data, len(table.rows)):
        row = table.rows[r]
        entity = _row_entity(row, resource_table)
        if entity is None:
            continue
        kind, name, row_label = entity
        for col in columns:
            if col.index >= len(row):
                continue
            raw = _last_line(row[col.index])
            value = parse_number(raw)
            if value is None:
                continue
            unit = col.unit or table_unit
            guessed = unit is None
            unit_text, std_unit, factor = unit or ("MT", "MT", 1.0)
            if col.metric == Metric.OB_REMOVAL and std_unit != "Mcum":
                unit_text, factor, guessed = unit_text, 1.0, True
            confidence = round(
                cell_confidence * col.mapping_confidence * (0.5 if guessed else 1), 3
            )
            box = (
                table.cells[r][col.index]
                if table.cells and col.index < len(table.cells[r])
                else None
            )
            facts.append(
                FactDraft(
                    metric=col.metric,
                    value_raw=raw,
                    value=value,
                    unit=unit_text,
                    value_std=round(value * factor, 6),
                    period_type=col.period_type,
                    period=col.period,
                    confidence=confidence,
                    page_no=page_no,
                    bbox=box or table.bbox,
                    label=f"{row_label} · {col.label}",
                    subsidiary=name if kind == "subsidiary" else None,
                    state=name if kind == "state" else None,
                    category=col.category,
                    unit_guessed=guessed,
                )
            )
    return facts


def _row_entity(row: list[str], resource_table: bool) -> tuple[str, str, str] | None:
    """(kind, code, label as printed) for the first cell(s) naming a subsidiary or state."""
    texts = [c.replace("\n", " ").strip() for c in row[:3] if c and not _is_numeric(c)]
    candidates = texts + [" ".join(texts[:2])] if len(texts) > 1 else texts
    for text in candidates:
        stripped = re.sub(r"^\d+\.?\s*", "", text)  # "10 Captives/Others" -> "Captives/Others"
        if resource_table:
            if name := state_name(stripped):
                return "state", name, text
            if stripped.lower() in ("total", "grand total", "all india", "india"):
                return "state", "ALL_INDIA", text
        elif code := subsidiary_code(stripped):
            return "subsidiary", code, text
    return None
