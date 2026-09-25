import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SimilarPqOut(BaseModel):
    """One similar past question. An approved reply links to its report; an uploaded PQ
    answer links to the document page and chunk that matched."""

    model_config = ConfigDict(from_attributes=True)

    kind: Literal["approved_reply", "pq_document"]
    title: str
    house: str | None  # "LS" | "RS"
    q_type: str | None  # "starred" | "unstarred"
    q_no: str | None
    answer_date: date | None
    snippet: str  # part of the question (or of the matching page) around the search words
    answer: str | None  # start of the reply, when known
    score: float  # fused rank score: only meaningful for ordering
    report_id: uuid.UUID | None
    document_id: uuid.UUID | None
    document_title: str | None
    page: int | None
    chunk_id: uuid.UUID | None
