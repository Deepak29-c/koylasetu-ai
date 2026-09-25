import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import House, QuestionType
from app.schemas.report import ReportOut


class PqDraftIn(BaseModel):
    """The PQ as the officer pastes it (guide 12, "New PQ reply" screen)."""

    house: House
    q_type: QuestionType = QuestionType.UNSTARRED
    q_no: str | None = Field(default=None, max_length=16)
    answer_date: date | None = None
    mp_name: str | None = Field(default=None, max_length=300)
    subject: str | None = Field(default=None, max_length=500)
    question_text: str = Field(min_length=10, max_length=20000)
    # When the reply has to be ready; the answer date is used when it is not given.
    due_date: date | None = None


class PqDraftOut(BaseModel):
    pq_id: uuid.UUID
    split_method: Literal["markers", "llm", "single"]
    report: ReportOut  # content_json holds header, blocks, sources and the plain text


class PqPartsIn(BaseModel):
    question_text: str = Field(max_length=20000)


class PqPartOut(BaseModel):
    part: str  # "a", "b"…, "क"… or "i", "ii"…
    text: str


class PqPartsOut(BaseModel):
    """How the question splits on its own markers, before anything is generated. "single"
    means no markers: at generation the model may still split it, or it is answered whole."""

    method: Literal["markers", "single"]
    intro: str
    parts: list[PqPartOut]
    max_parts: int  # parts after this many are not answered


class PqQuestionTextOut(BaseModel):
    filename: str
    text: str
    truncated: bool  # the file held more text than the question box takes
