import uuid
from typing import Literal

from pydantic import BaseModel, Field


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=4000)


class CitationOut(BaseModel):
    id: str  # "C1" (passage) or "F1" (figure): the id used inside the answer text
    kind: Literal["passage", "fact"]
    document_id: uuid.UUID
    document: str
    page: int
    bbox: list[float] | None
    text: str  # passage text, or the figure line for a fact
    chunk_id: uuid.UUID | None = None
    fact_id: uuid.UUID | None = None
    status: str | None = None  # facts: VERIFIED or FLAGGED (shown as unverified)


class TableOut(BaseModel):
    columns: list[str]
    rows: list[list[str]]


class AskOut(BaseModel):
    """Answer format of guide 9.3."""

    qa_id: uuid.UUID
    answer: str
    route: str
    table: TableOut | None = None
    citations: list[CitationOut]
    grounded: bool
    unmatched_numbers: list[str]  # as written in the answer, for red highlighting
    confidence: Literal["high", "medium", "low"]
    not_found: bool
    latency_ms: int


class FeedbackIn(BaseModel):
    score: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=2000)
