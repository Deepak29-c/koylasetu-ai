"""Map screen (#97): coal resources by state and production by subsidiary, for one period,
and coal resources by depth.

Figures come straight from the facts table (services/map_figures.py) and, for depth, from
the inventory's state-wise depth table (services/depth_figures.py); nothing is generated.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require
from app.core.rbac import Permission
from app.models import User
from app.models.enums import FactStatus, Metric
from app.schemas.map import DepthBandOut, DepthOut, DepthSourceOut, MapItemOut, MapOut
from app.services import depth_figures
from app.services.map_figures import base_statement, level_of, pick
from app.services.normalise import match_state

router = APIRouter(prefix="/map", tags=["map"])

MapMetric = Literal["coal_resource", "coal_production", "coal_offtake", "coking_coal_production"]
Category = Literal["Measured", "Indicated", "Inferred"]
Depth = Literal["0-300", "0-600", "300-600", "600-1200"]


def _depths(data: depth_figures.DepthData) -> list[str]:
    ranges = {b.depth_range for bands in depth_figures.by_state(data.rows).values() for b in bands}
    return sorted(ranges, key=lambda d: tuple(int(x) for x in d.split("-")))


def _by_depth(data: depth_figures.DepthData, depth: str, category: str | None) -> MapOut:
    """One depth band per state, e.g. every state's Measured resource at 0-300 m."""
    col = depth_figures.CATEGORY_COLUMN[category]
    items = []
    for state, bands in depth_figures.by_state(data.rows).items():
        band = next((b for b in bands if b.depth_range == depth), None)
        if band is None:
            continue
        first = band.rows[0]
        items.append(
            MapItemOut(
                key=state,
                value=round(getattr(band, col), 2),
                # Assam is printed in two sections; show both cells rather than a new number
                value_raw=" + ".join(_raw_cell(r, col) for r in band.rows),
                unit="million tonne",
                status=FactStatus.EXTRACTED.value,
                fact_id=None,
                document_id=str(first.document_id),
                document_title=data.titles.get(first.document_id, ""),
                page_no=first.page_no,
            )
        )
    items.sort(key=lambda i: -i.value)
    return MapOut(
        metric=Metric.COAL_RESOURCE.value,
        level="state",
        unit="MT",
        category=category,
        period=data.period,
        period_type="MONTH" if data.period else None,
        periods=data.periods,
        depth=depth,
        depths=_depths(data),
        items=items,
    )


def _raw_cell(row, col: str) -> str:
    """A column's cell as printed: M, I, Inferred (one cell, or exploration + mapping), Total."""
    raw = row.values_raw
    if col == "inferred":
        return " + ".join(raw[2:-1])
    return raw[{"measured": 0, "indicated": 1, "total": -1}[col]]


@router.get("/figures", response_model=MapOut)
def figures(
    metric: MapMetric = "coal_resource",
    category: Category | None = None,
    period: str | None = Query(None, max_length=16),
    depth: Depth | None = None,
    # The same figures the NUMERIC Q&A route answers from, so the same permission
    user: User = Depends(require(Permission.ASK_QUESTIONS)),
    db: Session = Depends(get_db),
) -> MapOut:
    m = Metric(metric)
    # Only resources are split by category and depth; production figures have neither
    if m != Metric.COAL_RESOURCE:
        category = depth = None
    depth_data = depth_figures.load(db, user, period) if m == Metric.COAL_RESOURCE else None
    if depth and depth_data is not None:
        return _by_depth(depth_data, depth, category)
    rows = db.execute(base_statement(m, category, user)).all()
    shown, periods, chosen = pick(rows, m, period)
    return MapOut(
        metric=m.value,
        level=level_of(m),
        unit="MT",  # every map metric is in million tonnes
        category=category,
        period=shown,
        period_type=chosen[0][0].period_type.value if chosen and chosen[0][0].period_type else None,
        periods=periods,
        depths=_depths(depth_data) if depth_data else [],
        items=[
            MapItemOut(
                key=fact.state if level_of(m) == "state" else fact.subsidiary,
                value=float(fact.value_std),
                value_raw=fact.value_raw,
                unit=fact.unit,
                status=fact.status.value,
                fact_id=str(fact.id),
                document_id=str(fact.document_id),
                document_title=title,
                page_no=fact.page_no,
            )
            for fact, title in chosen
        ],
    )


@router.get("/depth", response_model=DepthOut)
def depth_view(
    state: str | None = Query(None, max_length=100),
    period: str | None = Query(None, max_length=16),
    user: User = Depends(require(Permission.ASK_QUESTIONS)),
    db: Session = Depends(get_db),
) -> DepthOut:
    """A state's coal resources by depth band (all India when no state is given)."""
    name = match_state(state) if state else None
    data = depth_figures.load(db, user, period)
    rows = [r for r in data.rows if r.state == name] if (name or not state) else []
    bands = depth_figures.bands_of(rows)
    return DepthOut(
        state=name,
        unit="MT",
        period=data.period,
        periods=data.periods,
        total=round(sum(b.total for b in bands), 2),
        bands=[
            DepthBandOut(
                depth_range=b.depth_range,
                measured=round(b.measured, 2),
                indicated=round(b.indicated, 2),
                inferred=round(b.inferred, 2),
                total=round(b.total, 2),
                sources=[
                    DepthSourceOut(
                        document_id=str(r.document_id),
                        document_title=data.titles.get(r.document_id, ""),
                        page_no=r.page_no,
                        bbox=r.bbox,
                        label=" · ".join(
                            x
                            for x in (r.state or "All India", r.coal_type or "Total", r.depth_range)
                            if x
                        ),
                        values_raw=r.values_raw,
                    )
                    for r in b.rows
                ],
            )
            for b in bands
        ],
    )
