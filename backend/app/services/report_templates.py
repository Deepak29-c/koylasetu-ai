"""The report templates the system can draft (guide 10.1), described from the generators.

Every heading, column, row label and limit below is read from the generator modules'
constants, so this list changes when a generator changes. Section kinds and data-source codes
are words for the frontend to translate:

- kind: header | lines | bullets | table | sources
- source: form (typed by the user when drafting), facts (copied from the facts table by code),
  computed (worked out by code from those facts), qa (the Q&A service: retrieved passages and
  facts, written by the local model and checked against the cited source), model (written by
  the local model from the table rows, by rule when it is not available), citations (the
  document page behind every figure).

Pure: no database, no model.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ReportType
from app.services import briefing_note, monthly_report, pq_reply, report_builder


@dataclass(frozen=True)
class Limit:
    key: str
    value: float


@dataclass(frozen=True)
class TemplateSection:
    key: str
    kind: str
    heading: str | None = None
    sources: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    rows: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    chart: bool = False
    optional: bool = False  # only printed when there is something to show
    limits: tuple[Limit, ...] = ()


@dataclass(frozen=True)
class Template:
    report_type: ReportType
    title: str | None
    generator: str  # module that drafts it
    sections: tuple[TemplateSection, ...]


def _pq_reply() -> Template:
    m = pq_reply
    return Template(
        ReportType.PQ_REPLY,
        m.MINISTRY,
        m.__name__,
        (
            TemplateSection(
                "header", "header", rows=(m.MINISTRY, *m.HOUSE_LABEL.values()), sources=("form",)
            ),
            TemplateSection("question", "lines", m.DEFAULT_INTRO, sources=("form",)),
            TemplateSection("answer", "header", m.ANSWER_HEADING, rows=(m.MINISTER_LINE,)),
            TemplateSection(
                "statement", "lines", m.STATEMENT_HEADING, sources=("form",), optional=True
            ),
            TemplateSection(
                "parts", "lines", sources=("qa", "facts"), limits=(Limit("max_parts", m.MAX_PARTS),)
            ),
            TemplateSection(
                "annexures",
                "table",
                m.ANNEXURE_PREFIX,
                sources=("qa", "facts"),
                optional=True,
                limits=(Limit("annexure_rows", m.ANNEXURE_ROWS),),
            ),
            TemplateSection("sources", "sources", m.SOURCES_HEADING, sources=("citations",)),
        ),
    )


def _monthly() -> Template:
    m = monthly_report
    tables = tuple(
        TemplateSection(
            spec.key,
            "table",
            spec.heading,
            sources=("facts", "computed"),
            columns=tuple(m.columns(spec)),
            rows=tuple(label for _, label in m.ROWS),
            metrics=tuple(x for x in (spec.metric, spec.target_metric) if x),
            chart=True,
        )
        for spec in m.TABLES
    )
    return Template(
        ReportType.MONTHLY,
        m.TITLE,
        m.__name__,
        (
            TemplateSection("summary", "lines", m.SUMMARY_HEADING, sources=("facts", "computed")),
            *tables,
            TemplateSection(
                "remarks",
                "lines",
                m.REMARKS_HEADING,
                sources=("model",),
                limits=(
                    Limit("max_remarks", m.MAX_REMARKS),
                    Limit("remark_threshold_pct", m.REMARK_THRESHOLD),
                ),
            ),
            TemplateSection(
                "sources", "sources", report_builder.SOURCES_HEADING, sources=("citations",)
            ),
        ),
    )


def _briefing() -> Template:
    m = briefing_note
    return Template(
        ReportType.BRIEFING,
        m.TITLE,
        m.__name__,
        (
            TemplateSection(
                "key_figures",
                "table",
                m.KEY_FIGURES_HEADING,
                sources=("facts", "computed"),
                columns=tuple(m.KEY_COLUMNS),
                metrics=tuple(m.METRIC_NAME),
            ),
            TemplateSection(
                "trend",
                "table",
                m.TREND_HEADING,
                sources=("facts",),
                chart=True,
                optional=True,
                limits=(Limit("max_trend", m.MAX_TREND),),
            ),
            TemplateSection(
                "key_points",
                "bullets",
                m.KEY_POINTS_HEADING,
                sources=("qa",),
                limits=(Limit("max_points", m.MAX_KEY_POINTS),),
            ),
            TemplateSection(
                "steps",
                "bullets",
                m.STEPS_HEADING,
                sources=("qa",),
                limits=(Limit("max_points", m.MAX_STEPS),),
            ),
            TemplateSection(
                "sources", "sources", report_builder.SOURCES_HEADING, sources=("citations",)
            ),
        ),
    )


def templates() -> list[Template]:
    return [_pq_reply(), _monthly(), _briefing()]
