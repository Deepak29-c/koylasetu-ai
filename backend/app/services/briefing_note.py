"""Briefing note, first draft (guide 10.1 "briefing", workflow W6).

topic (+ optional month range) ->
- KEY FIGURES: facts picked by code from the metric and subsidiary words in the topic
  (production, despatch, target, coking, OB, imports; ECL…NEC, CIL, SCCL, captive, India):
  the latest month and latest financial year in range, each with the same period a year
  before and the change % computed by code. Missing figures show "–".
- TREND: the monthly (or yearly) series of the first figure, as a table and a bar chart.
- KEY POINTS (up to 7 bullets) and RECENT STEPS / INITIATIVES (up to 5): from the Q&A
  service's public entry point (qa.ask), so the same retrieval and routing apply; then the
  PQ reply's stricter rule (pq_reply.keep_sourced): a sentence with a figure must cite a
  passage and the figure must be in it, otherwise it is dropped and its figures listed.
- SOURCES: document + page for every figure and point.

Everything below except `draft_briefing` is pure (no database, no model).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.llm import client
from app.models.enums import Metric
from app.services import pq_reply, qa
from app.services.monthly_report import month_short, parse_month
from app.services.normalise import ALL_INDIA, match_subsidiaries
from app.services.report_builder import (
    NOT_FOUND_CELL,
    NOT_FOUND_NOTE,
    UNVERIFIED_MARK,
    UNVERIFIED_NOTE,
    DocSources,
    FactRow,
    best_fact,
    fetch_facts,
    fmt_value,
    render_text,
    section,
)

MAX_KEY_POINTS = 7
MAX_STEPS = 5
MAX_TREND = 12
NOT_FOUND_POINT = "Information not found in available documents."

# Topic words -> metric (the router-like filter). Order matters: "coking coal production"
# is coking, "production target" is the target.
_METRIC_WORDS: list[tuple[str, re.Pattern[str]]] = [
    (Metric.COKING_COAL_PRODUCTION.value, re.compile(r"\bcoking\b|कोकिंग", re.I)),
    (Metric.PRODUCTION_TARGET.value, re.compile(r"\btargets?\b|लक्ष्य", re.I)),
    (
        Metric.COAL_OFFTAKE.value,
        re.compile(r"\bdespatch|\bdispatch|\boff\s*-?\s*take|उठाव|प्रेषण", re.I),
    ),
    (Metric.OB_REMOVAL.value, re.compile(r"\bover\s*-?\s*burden|\bob\b|\bobr\b", re.I)),
    (Metric.COAL_IMPORT.value, re.compile(r"\bimports?\b|आयात", re.I)),
    (Metric.COAL_PRODUCTION.value, re.compile(r"\bproduc|\boutput\b|उत्पादन", re.I)),
]
_NON_COKING = re.compile(r"\bnon\s*-?\s*coking", re.I)
_INDIA = re.compile(r"(?<!coal )\bindia\b|\bcountry\b|भारत|देश", re.I)  # not "Coal India"
DEFAULT_METRICS = [Metric.COAL_PRODUCTION.value, Metric.COAL_OFFTAKE.value]
DEFAULT_SUBSIDIARIES = [ALL_INDIA, "CIL"]
METRIC_NAME = {
    Metric.COAL_PRODUCTION.value: "Coal production",
    Metric.COAL_OFFTAKE.value: "Coal despatch",
    Metric.PRODUCTION_TARGET.value: "Production target",
    Metric.COKING_COAL_PRODUCTION.value: "Coking coal production",
    Metric.OB_REMOVAL.value: "Overburden removal",
    Metric.COAL_IMPORT.value: "Coal import",
}
SUBSIDIARY_NAME = {ALL_INDIA: "All India", "CAPTIVE": "Captive/Others"}
KEY_COLUMNS = ["Figure", "Period", "Value", "Year before", "Change (%)", "Source"]


def unit_of(metric: str) -> str:
    return "Mcum" if metric == Metric.OB_REMOVAL.value else "MT"


# --- what the topic asks for ---------------------------------------------------------------------


def topic_metrics(topic: str) -> list[str]:
    text = _NON_COKING.sub(" ", topic)
    found = [m for m, rx in _METRIC_WORDS if rx.search(text)]
    if Metric.COKING_COAL_PRODUCTION.value in found and Metric.COAL_PRODUCTION.value in found:
        found.remove(Metric.COAL_PRODUCTION.value)  # "coking coal production" is one metric
    return found or list(DEFAULT_METRICS)


def topic_subsidiaries(topic: str) -> list[str]:
    codes, _ = match_subsidiaries(topic)
    if _INDIA.search(topic):
        codes.add(ALL_INDIA)
    order = ["INDIA", "CIL", "ECL", "BCCL", "CCL", "NCL", "WCL", "SECL", "MCL", "NEC", "SCCL"]
    ranked = sorted(codes, key=lambda c: order.index(c) if c in order else len(order))
    return ranked or list(DEFAULT_SUBSIDIARIES)


# --- periods -------------------------------------------------------------------------------------

_FY = re.compile(r"^FY (\d{4})-(\d{2})$")


def fy_months(period: str) -> tuple[str, str] | None:
    """ "FY 2024-25" -> ("2024-04", "2025-03")."""
    m = _FY.match(period or "")
    if not m:
        return None
    start = int(m.group(1))
    return f"{start}-04", f"{start + 1}-03"


def in_range(period: str | None, start: str | None, end: str | None) -> bool:
    """A month inside [start, end], or a financial year that overlaps it."""
    if not period:
        return False
    fy = fy_months(period)
    first, last = fy if fy else (period, period)
    if not fy and not re.fullmatch(r"\d{4}-\d{2}", period):
        return False
    return (start is None or last >= start) and (end is None or first <= end)


def year_before(period: str) -> str:
    fy = _FY.match(period)
    if fy:
        start = int(fy.group(1)) - 1
        return f"FY {start}-{(start + 1) % 100:02d}"
    year, mon = parse_month(period)
    return f"{year - 1}-{mon:02d}"


def period_label(period: str) -> str:
    return period if period.startswith("FY") else month_short(period)


# --- key figures and trend -----------------------------------------------------------------------


def _group(facts: list[FactRow]) -> dict[tuple[str, str | None, str | None], list[FactRow]]:
    out: dict[tuple, list[FactRow]] = {}
    for f in facts:
        out.setdefault((f.metric, f.subsidiary, f.period), []).append(f)
    return out


def _shown(fact: FactRow | None) -> str:
    if fact is None:
        return NOT_FOUND_CELL
    return fmt_value(fact.value_std) + ("" if fact.verified else UNVERIFIED_MARK)


def figure_name(metric: str, code: str) -> str:
    return (
        f"{METRIC_NAME.get(metric, metric)} - {SUBSIDIARY_NAME.get(code, code)} ({unit_of(metric)})"
    )


@dataclass
class KeyFigures:
    table: dict | None
    trend: dict | None
    trend_title: str
    unverified: bool
    missing: bool


def key_figures(
    facts: list[FactRow],
    metrics: list[str],
    codes: list[str],
    registry: DocSources,
    start: str | None = None,
    end: str | None = None,
) -> KeyFigures:
    groups = _group(facts)
    rows: list[list[str]] = []
    trend = None
    trend_title = ""
    unverified = missing = False
    for metric in metrics:
        for code in codes:
            periods = {
                p for (m, c, p) in groups if m == metric and c == code and in_range(p, start, end)
            }
            months = sorted(p for p in periods if not p.startswith("FY"))
            fys = sorted(p for p in periods if p.startswith("FY"))
            for period in months[-1:] + fys[-1:]:  # latest month, latest FY
                now, _ = best_fact(groups.get((metric, code, period), []))
                if now is None:
                    continue
                before_period = year_before(period)
                before, _ = best_fact(groups.get((metric, code, before_period), []))
                where = f"key:{metric}:{code}:{period}"
                sids = [registry.add_fact(now, where)]
                if before is not None:
                    sids.append(registry.add_fact(before, f"key:{metric}:{code}:{before_period}"))
                change = None
                if before is not None and before.value_std:
                    change = round((now.value_std / before.value_std - 1) * 100, 2)
                row_unverified = not now.verified or (before is not None and not before.verified)
                unverified |= row_unverified
                missing |= before is None
                mark = UNVERIFIED_MARK if row_unverified else ""
                rows.append(
                    [
                        figure_name(metric, code),
                        period_label(period),
                        _shown(now),
                        _shown(before),
                        NOT_FOUND_CELL if change is None else fmt_value(change) + mark,
                        ", ".join(dict.fromkeys(sids)),
                    ]
                )
            if trend is None:
                series = months if len(months) >= 2 else fys
                if len(series) >= 2:
                    trend_rows = []
                    for period in series[-MAX_TREND:]:
                        f, _ = best_fact(groups.get((metric, code, period), []))
                        if f is None:
                            continue
                        sid = registry.add_fact(f, f"trend:{metric}:{code}:{period}")
                        unverified |= not f.verified
                        trend_rows.append([period_label(period), _shown(f), sid])
                    trend = {
                        "columns": ["Period", figure_name(metric, code), "Source"],
                        "rows": trend_rows,
                    }
                    trend_title = f"TREND: {figure_name(metric, code).upper()}"
    table = {"columns": KEY_COLUMNS, "rows": rows} if rows else None
    return KeyFigures(table, trend, trend_title, unverified, missing)


# --- key points from the Q&A service -------------------------------------------------------------


def points_from_answer(
    answer: object, registry: DocSources, where: str, limit: int
) -> tuple[list[str], list[str], bool]:
    """Bullets from one Q&A answer: grounded sentences only, citations renumbered to S1…
    Returns (bullets, removed figures, not_found)."""
    local: dict[str, object] = {}
    for key in ("citations", "passages", "facts"):
        for item in getattr(answer, key, None) or []:
            local.setdefault(item.ref, item)
    if getattr(answer, "not_found", False):
        return [NOT_FOUND_POINT], [], True
    kept, removed = pq_reply.keep_sourced(answer.answer.strip(), local)
    mapping: dict[str, str] = {}

    def renumber(m: re.Match) -> str:
        ref = m.group(1)
        if ref not in local:
            return ""
        if ref not in mapping:
            s = pq_reply.source_of(local[ref])
            mapping[ref] = registry.add(
                document_id=s.document_id,
                document=s.document,
                page=s.page,
                where=where,
                fact_id=s.source_id if s.kind == "fact" else None,
                chunk_id=s.source_id if s.kind == "chunk" else None,
            )
        return f"[{mapping[ref]}]"

    bullets = []
    for line in pq_reply.split_lines(kept):
        for s in pq_reply.sentences(pq_reply._BULLET.sub("", line)):
            text = re.sub(r"\[\s*([CF]\d+)\s*\]", renumber, s).strip()
            text = re.sub(r"\s+([.,;।])", r"\1", text)
            if re.sub(r"\[S\d+\]|[\W_]", "", text):
                bullets.append(text)
    if not bullets:
        return [NOT_FOUND_POINT], removed, True
    return bullets[:limit], removed, False


def key_points_query(topic: str) -> str:
    return f"{topic.strip()}: key facts, figures and current status"


def steps_query(topic: str) -> str:
    return f"{topic.strip()}: recent steps and initiatives taken"


# --- the whole draft -----------------------------------------------------------------------------


@dataclass
class BriefingDraft:
    content: dict
    links: list[dict]


def range_text(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{month_short(start)} to {month_short(end)}"
    if start:
        return f"from {month_short(start)}"
    if end:
        return f"up to {month_short(end)}"
    return ""


def build_content(
    topic: str,
    facts: list[FactRow],
    points_answer: object,
    steps_answer: object,
    *,
    start: str | None = None,
    end: str | None = None,
) -> BriefingDraft:
    """Pure: facts + two Q&A answers -> content_json + citation links."""
    registry = DocSources()
    metrics, codes = topic_metrics(topic), topic_subsidiaries(topic)
    figures = key_figures(facts, metrics, codes, registry, start, end)
    notes = []
    if figures.unverified:
        notes.append(UNVERIFIED_NOTE)
    if figures.missing:
        notes.append(NOT_FOUND_NOTE)
    sections = []
    if figures.table:
        sections.append(section("key_figures", "KEY FIGURES", table=figures.table, notes=notes))
    else:
        sections.append(
            section(
                "key_figures",
                "KEY FIGURES",
                ["No figures on this topic were found in the facts table."],
            )
        )
    if figures.trend:
        sections.append(section("trend", figures.trend_title, table=figures.trend))

    points, removed_points, points_nf = points_from_answer(
        points_answer, registry, "key_points", MAX_KEY_POINTS
    )
    steps, removed_steps, steps_nf = points_from_answer(steps_answer, registry, "steps", MAX_STEPS)
    sections.append(
        section("key_points", "KEY POINTS", points, bullets=True, removed_numbers=removed_points)
    )
    sections.append(
        section(
            "steps",
            "RECENT STEPS / INITIATIVES",
            steps,
            bullets=True,
            removed_numbers=removed_steps,
        )
    )
    period = range_text(start, end)
    content = {
        "kind": "briefing",
        "topic": topic,
        "from": start,
        "to": end,
        "title": "BRIEFING NOTE",
        "subtitle": topic.strip() + (f" ({period})" if period else ""),
        "metrics": metrics,
        "subsidiaries": codes,
        "sections": sections,
        "sources": registry.sources,
        "warnings": [],
        "points_not_found": points_nf,
        "steps_not_found": steps_nf,
    }
    content["text"] = render_text(content)
    return BriefingDraft(content, registry.links())


def draft_briefing(
    db,
    user,
    topic: str,
    *,
    start: str | None = None,
    end: str | None = None,
    ask: Callable[..., object] | None = None,
    check_model: Callable[[], None] | None = None,
) -> BriefingDraft:
    """Raises client.LlmUnavailable up front if the model is not there (the key points need
    it), rather than saving a note whose points all say "not found"."""
    (check_model or client.ensure_available)()
    ask = ask or qa.ask
    metrics, codes = topic_metrics(topic), topic_subsidiaries(topic)
    facts = fetch_facts(db, user, metrics=metrics, subsidiaries=codes)
    points = ask(db, user, key_points_query(topic))
    steps = ask(db, user, steps_query(topic))
    return build_content(topic, facts, points, steps, start=start, end=end)
