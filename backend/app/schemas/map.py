from typing import Literal

from pydantic import BaseModel


class MapItemOut(BaseModel):
    """One shaded state or one subsidiary circle, with the source of its figure."""

    key: str  # state name as stored in facts ("Odisha") or subsidiary code ("MCL")
    value: float  # in the metric's standard unit (MT, or Mcum for OB)
    value_raw: str  # the cell text exactly as in the source
    unit: str | None  # the source's own unit
    status: str  # VERIFIED / EXTRACTED / FLAGGED; the map labels anything not verified
    fact_id: str | None  # None for a depth figure (it comes from depth_resources)
    document_id: str
    document_title: str
    page_no: int


class MapOut(BaseModel):
    metric: str
    level: Literal["state", "subsidiary"]
    unit: str  # standard unit of every value
    category: str | None
    period: str | None  # the period shown; None when there are no figures at all
    period_type: str | None
    periods: list[str]  # every period with figures for this metric and category, newest first
    depth: str | None = None  # the depth band shown ("0-300"), None = all depths
    depths: list[str] = []  # depth bands the resource figures can be split into
    items: list[MapItemOut]


class DepthSourceOut(BaseModel):
    """A printed row a depth figure was read from."""

    document_id: str
    document_title: str
    page_no: int
    bbox: list[float] | None
    label: str  # "JHARKHAND · TOTAL · 0-300", as printed
    values_raw: list[str]


class DepthBandOut(BaseModel):
    depth_range: str  # "0-300"
    measured: float
    indicated: float
    inferred: float
    total: float
    sources: list[DepthSourceOut]


class DepthOut(BaseModel):
    """One state's (or all India's) coal resources by depth, shallow first."""

    state: str | None  # None = all India
    unit: str
    period: str | None
    periods: list[str]
    bands: list[DepthBandOut]
    total: float
