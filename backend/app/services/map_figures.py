"""Figures for the Map screen: one value per state (coal resources) or per subsidiary
(production, offtake, coking coal) for one period.

Same rules as the NUMERIC route (services/facts_query.py): only the user's units, never
REJECTED facts or values whose unit could not be converted, and a verified figure wins over
an unverified one for the same place. Facts with no period are left out, because the map
could not say which period they belong to.
"""

from __future__ import annotations

from sqlalchemy import Select, select

from app.core.deps import scope_to_user
from app.models import Document, Fact, User
from app.models.enums import FactStatus, Metric, PeriodType
from app.services.normalise import CIL_SUBSIDIARIES

# Companies drawn as circles: every CIL subsidiary plus SCCL. CIL, INDIA and CAPTIVE are
# totals of the others, not places.
MAP_SUBSIDIARIES = sorted(CIL_SUBSIDIARIES | {"SCCL"})


def level_of(metric: Metric) -> str:
    return "state" if metric == Metric.COAL_RESOURCE else "subsidiary"


def base_statement(metric: Metric, category: str | None, user: User) -> Select:
    """Every usable fact for the metric and category, with its document title."""
    stmt = (
        select(Fact, Document.title)
        .join(Document, Document.id == Fact.document_id)
        .where(
            Fact.metric == metric,
            Fact.status != FactStatus.REJECTED,
            Fact.value_std.is_not(None),
            Fact.period.is_not(None),
            # A year-to-date "2024-12" would otherwise be taken for the month of December
            Fact.period_type.is_distinct_from(PeriodType.YTD),
        )
    )
    if level_of(metric) == "state":
        stmt = stmt.where(Fact.state.is_not(None), Fact.subsidiary.is_(None))
        # The total resource has no category; Measured / Indicated / Inferred do
        if category:
            stmt = stmt.where(Fact.category.like(f"{category}%"))
        else:
            stmt = stmt.where(Fact.category.is_(None))
    else:
        stmt = stmt.where(Fact.subsidiary.in_(MAP_SUBSIDIARIES))
    return scope_to_user(stmt, Document, user)


def pick(rows: list, metric: Metric, period: str | None) -> tuple[str | None, list[str], list]:
    """(period shown, periods available newest first, one (fact, title) per place).

    The asked period is used when it has figures, else the newest one. Several facts for the
    same place and period (two documents, or a re-extraction): verified beats unverified,
    then the higher confidence wins."""
    periods = sorted({fact.period for fact, _ in rows}, reverse=True)
    if not periods:
        return None, [], []
    shown = period if period in periods else periods[0]
    by_place: dict[str, tuple] = {}
    for fact, title in rows:
        if fact.period != shown:
            continue
        place = fact.state if level_of(metric) == "state" else fact.subsidiary
        rank = (fact.status == FactStatus.VERIFIED, fact.confidence or 0.0)
        if place not in by_place or rank > by_place[place][0]:
            by_place[place] = (rank, fact, title)
    chosen = [(fact, title) for _, fact, title in by_place.values()]
    chosen.sort(key=lambda ft: -float(ft[0].value_std))
    return shown, periods, chosen
