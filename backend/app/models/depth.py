import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class DepthResource(Entity):
    """One printed row of a state-wise, depth-wise coal resource table (#97), e.g. Table II
    of the National Coal Inventory: "JHARKHAND · MEDIUM COKING · 0-300 · 8034.62 3410.47 …".

    Kept out of `facts` on purpose: these rows break a state's resource down by depth and
    coal type, so every existing facts query (Q&A, reports, validation) would otherwise add
    them to the state totals. Every value is the cell as printed; rows are only stored when
    their numbers add up (worker/depth.py)."""

    __tablename__ = "depth_resources"
    __table_args__ = (Index("ix_depth_resources_lookup", "state", "period"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_no: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[list[float] | None] = mapped_column(JSONB)  # the printed line
    period: Mapped[str] = mapped_column(String(16))  # "as on 01.04.2025" -> "2025-04"
    section: Mapped[str | None] = mapped_column(String(16))  # GONDWANA / TERTIARY
    state: Mapped[str | None] = mapped_column(String(100))  # None = the all-India total
    # PRIME COKING, NON-COKING COAL, High Sulphur…; None on a "TOTAL FOR <state>" row
    coal_type: Mapped[str | None] = mapped_column(String(32))
    depth_range: Mapped[str] = mapped_column(String(16))  # "0-300", "300-600", "0-1200"
    is_total: Mapped[bool] = mapped_column(Boolean)  # the block's total row, not a depth band
    measured: Mapped[float] = mapped_column(Numeric)
    indicated: Mapped[float] = mapped_column(Numeric)
    inferred: Mapped[float] = mapped_column(Numeric)  # exploration + mapping columns
    total: Mapped[float] = mapped_column(Numeric)
    values_raw: Mapped[list[str]] = mapped_column(JSONB)  # the cells exactly as printed
