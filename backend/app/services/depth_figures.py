"""Depth-wise coal resources (#97) for the Map screen, from the rows worker/depth.py stored.

A state's bands are its printed "TOTAL FOR <state>" rows; a state with one coal type has no
such block, so its coal-type rows are used instead. Assam is printed twice (Gondwana and
Tertiary coalfields) and its two sections are added. All India is the GRAND TOTAL block.
Only the depth bands are used (0-300, 300-600, 600-1200 and Jharia's 0-600), never the
block totals, so nothing is counted twice.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import scope_to_user
from app.models import DepthResource, Document, User

COLUMNS = ("measured", "indicated", "inferred", "total")
# Map picker category -> column
CATEGORY_COLUMN = {
    None: "total",
    "Measured": "measured",
    "Indicated": "indicated",
    "Inferred": "inferred",
}


@dataclass
class Band:
    depth_range: str
    measured: float = 0.0
    indicated: float = 0.0
    inferred: float = 0.0
    total: float = 0.0
    rows: list = field(default_factory=list)  # the printed rows added into it

    @property
    def span(self) -> tuple[int, int]:
        a, b = self.depth_range.split("-")
        return int(a), int(b)


def bands_of(rows: list) -> list[Band]:
    """Depth bands of one place (a state, or all India with state None), shallow first."""
    by_section: dict[str | None, list] = {}
    for r in rows:
        by_section.setdefault(r.section, []).append(r)
    bands: dict[str, Band] = {}
    for section_rows in by_section.values():
        state_level = [r for r in section_rows if r.coal_type is None and not r.is_total]
        typed = [r for r in section_rows if r.coal_type is not None and not r.is_total]
        for r in state_level or typed:
            band = bands.setdefault(r.depth_range, Band(r.depth_range))
            for col in COLUMNS:
                setattr(band, col, getattr(band, col) + float(getattr(r, col)))
            band.rows.append(r)
    return sorted(bands.values(), key=lambda b: b.span)


def one_document_per_period(rows: list) -> list:
    """If the same inventory was uploaded twice, use only the copy with the most rows."""
    counts = Counter((r.period, r.document_id) for r in rows)
    best: dict[str, tuple] = {}
    for (period, doc), n in counts.items():
        if period not in best or n > best[period][1]:
            best[period] = (doc, n)
    return [r for r in rows if best[r.period][0] == r.document_id]


def statement(user: User):
    """Every depth row the user may see, with its document title."""
    stmt = select(DepthResource, Document.title).join(
        Document, Document.id == DepthResource.document_id
    )
    return scope_to_user(stmt, Document, user)


@dataclass
class DepthData:
    period: str | None
    periods: list[str]  # newest first
    rows: list  # of the chosen period, one document
    titles: dict  # document_id -> title


def load(db: Session, user: User, period: str | None) -> DepthData:
    found = db.execute(statement(user)).all()
    titles = {r.document_id: title for r, title in found}
    rows = one_document_per_period([r for r, _ in found])
    periods = sorted({r.period for r in rows}, reverse=True)
    if not periods:
        return DepthData(None, [], [], titles)
    shown = period if period in periods else periods[0]
    return DepthData(shown, periods, [r for r in rows if r.period == shown], titles)


def by_state(rows: list) -> dict[str, list[Band]]:
    """Bands per state (all-India rows left out)."""
    states: dict[str, list] = {}
    for r in rows:
        if r.state is not None:
            states.setdefault(r.state, []).append(r)
    return {s: bands_of(rs) for s, rs in states.items()}
