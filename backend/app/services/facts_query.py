"""Facts query for the NUMERIC route (guide 9.1): numbers come from the database, never the model.

The query is built from the router's filters with bound parameters. The model never writes
SQL, so there is nothing to inject. It runs in its own READ ONLY transaction with a 5 s
statement timeout (guide 9.1), only on the user's org units, never on REJECTED facts, and
verified facts win over unverified ones for the same figure.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.deps import scope_to_user
from app.models import Document, Fact, User
from app.models.enums import FactStatus, Metric, PeriodType
from app.services.normalise import ALL_INDIA, CIL_SUBSIDIARIES
from app.services.router import Filters

MAX_ROWS = 60
TIMEOUT_MS = 5000


@dataclass
class FactRow:
    ref: str  # "F1", "F2"… the id the model cites
    fact_id: uuid.UUID
    metric: str
    subsidiary: str | None
    state: str | None
    category: str | None
    period_type: str | None
    period: str | None
    value_raw: str
    unit: str | None
    value_std: float
    status: str
    document_id: uuid.UUID
    document_title: str
    page_no: int
    bbox: list[float] | None

    @property
    def who(self) -> str:
        return {ALL_INDIA: "All India", "CAPTIVE": "Captive/Others"}.get(
            self.subsidiary or self.state or "", self.subsidiary or (self.state or "").title()
        )

    @property
    def period_text(self) -> str:
        if self.period_type == PeriodType.YTD:
            return f"April to {_month_name(self.period)} (cumulative)"
        if self.period_type == PeriodType.MONTH:
            if self.metric == Metric.COAL_RESOURCE:  # a stock figure: "as on" that month
                return f"as on {_month_name(self.period)}"
            return _month_name(self.period)
        if self.period_type == PeriodType.AS_ON:
            y, m, d = self.period.split("-")
            return f"as on {d}.{m}.{y}"
        return self.period or "period unknown"

    @property
    def std_unit(self) -> str:
        return "Mcum" if self.metric == Metric.OB_REMOVAL else "MT"


def _month_name(period: str | None) -> str:
    if not period:
        return "period unknown"
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    y, m = period.split("-")[:2]
    return f"{names[int(m) - 1]} {y}"


def _statement(f: Filters, user: User):
    stmt = (
        select(Fact, Document.title)
        .join(Document, Document.id == Fact.document_id)
        .where(
            Fact.metric.in_(f.metrics),
            Fact.status != FactStatus.REJECTED,
            Fact.value_std.is_not(None),  # a unit we couldn't convert is not a usable figure
        )
    )
    resource = f.metrics == [Metric.COAL_RESOURCE]
    subsidiaries = list(f.subsidiaries)
    if f.breakdown and subsidiaries == ["CIL"]:
        # "subsidiary-wise ... of CIL" means every CIL subsidiary, plus the CIL total
        subsidiaries = [*CIL_SUBSIDIARIES, "CIL"]
    if subsidiaries:
        stmt = stmt.where(Fact.subsidiary.in_(subsidiaries))
    elif f.states:
        stmt = stmt.where(Fact.state.in_(f.states))
    elif not f.breakdown:
        # Nothing named: the national figure (India total, or CIL for company tables)
        stmt = stmt.where(
            Fact.subsidiary == ALL_INDIA if resource else Fact.subsidiary.in_([ALL_INDIA, "CIL"])
        )
    elif resource:
        stmt = stmt.where(Fact.state.is_not(None))
    else:
        stmt = stmt.where(Fact.subsidiary.is_not(None))

    if resource:
        # Measured / Indicated / Inferred; the total resource has no category
        if f.category:
            stmt = stmt.where(Fact.category.like(f"{f.category}%"))
        else:
            stmt = stmt.where(Fact.category.is_(None))
    if f.period_type and f.periods:
        stmt = stmt.where(Fact.period_type == f.period_type, Fact.period.in_(f.periods))
    return scope_to_user(stmt, Document, user).order_by(Fact.period.desc(), Fact.subsidiary)


def _run(stmt) -> list:
    """Execute in a separate READ ONLY transaction with a statement timeout."""
    with SessionLocal() as ro:
        ro.execute(text("SET TRANSACTION READ ONLY"))
        ro.execute(text(f"SET LOCAL statement_timeout = {TIMEOUT_MS}"))
        rows = ro.execute(stmt.limit(MAX_ROWS * 4)).all()
        ro.expunge_all()  # keep the loaded values: rollback would otherwise expire them
        ro.rollback()
    return rows


def query_facts(db: Session, user: User, f: Filters, run=_run) -> list[FactRow]:
    """Facts matching the filters. If a period was asked for but none match exactly (e.g. a
    full FY when only year-to-date figures exist), returns nothing, so the answer never
    silently swaps in a different period. When no period was asked, uses the latest one."""
    if f.coking:
        # Coking coal is stored only as its own metric (coking_coal_production); an overall
        # despatch or resource figure must not be given as the coking-coal one.
        f = replace(f, metrics=[m for m in f.metrics if m == Metric.COKING_COAL_PRODUCTION])
    if not f.metrics:
        return []
    rows = run(_statement(f, user))
    if not f.periods and rows:
        latest = {}
        for fact, _ in rows:  # latest period per metric, preferring monthly figures
            k = fact.metric
            rank = (fact.period or "", fact.period_type == PeriodType.MONTH)
            if k not in latest or rank > latest[k]:
                latest[k] = rank
        rows = [
            (fa, t)
            for fa, t in rows
            if (fa.period or "", fa.period_type == PeriodType.MONTH) == latest[fa.metric]
        ]

    # One value per figure: verified beats flagged; otherwise the first (newest period) wins
    best: dict[tuple, tuple] = {}
    for fact, title in rows:
        key = (
            fact.metric,
            fact.subsidiary,
            fact.state,
            fact.category,
            fact.period_type,
            fact.period,
        )
        if key not in best or (
            best[key][0].status != FactStatus.VERIFIED and fact.status == FactStatus.VERIFIED
        ):
            best[key] = (fact, title)

    out = []
    for fact, title in list(best.values())[:MAX_ROWS]:
        out.append(
            FactRow(
                ref=f"F{len(out) + 1}",
                fact_id=fact.id,
                metric=fact.metric.value,
                subsidiary=fact.subsidiary,
                state=fact.state,
                category=fact.category,
                period_type=fact.period_type.value if fact.period_type else None,
                period=fact.period,
                value_raw=fact.value_raw,
                unit=fact.unit,
                value_std=float(fact.value_std),
                status=fact.status.value,
                document_id=fact.document_id,
                document_title=title,
                page_no=fact.page_no,
                bbox=fact.bbox,
            )
        )
    return out
