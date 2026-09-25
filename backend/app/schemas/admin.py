from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ThresholdOut(BaseModel):
    key: str
    value: float
    unit: str


class RuleOut(BaseModel):
    """One validation rule (worker/validate.py RULES) and its open issues in the caller's units."""

    code: str
    name: str
    checks: str
    severities: list[str]
    thresholds: list[ThresholdOut]
    uses_other_documents: bool
    open_issues: int


class LimitOut(BaseModel):
    key: str
    value: float


class TemplateSectionOut(BaseModel):
    key: str
    kind: str
    heading: str | None
    sources: list[str]
    columns: list[str]
    rows: list[str]
    metrics: list[str]
    chart: bool
    optional: bool
    limits: list[LimitOut]


class TemplateOut(BaseModel):
    report_type: str
    title: str | None
    generator: str
    sections: list[TemplateSectionOut]


class CheckOut(BaseModel):
    key: str
    status: Literal["ok", "warn", "error"]
    code: str
    message: str
    details: dict[str, Any]


class QueueOut(BaseModel):
    name: str
    queued: int
    failed: int


class ModelOut(BaseModel):
    name: str
    role: Literal["llm", "embed"]
    pulled: bool | None


class StorageOut(BaseModel):
    path: str
    free_bytes: int
    total_bytes: int


class FlagsOut(BaseModel):
    ingest_inline: bool
    allow_external_calls: bool


class SystemStatusOut(BaseModel):
    checked_at: datetime
    version: str
    overall: Literal["ok", "warn", "error"]
    checks: list[CheckOut]
    queues: list[QueueOut] | None  # None when Redis is not used or not reachable
    workers: int | None
    models: list[ModelOut]
    storage: StorageOut | None
    documents: dict[str, int] | None  # by status, in the caller's units
    flags: FlagsOut
