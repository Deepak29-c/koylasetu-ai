import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import House, QuestionType


class WordOut(BaseModel):
    text: str
    weight: int  # number of questions / passages the word appears in


class WordCloudOut(BaseModel):
    source: str
    texts: int  # how many questions / passages were counted
    words: list[WordOut]


class TopicOut(BaseModel):
    id: uuid.UUID
    topic_no: int
    label: str
    keywords: list[str]
    size: int
    period_counts: dict  # {"year": {"2021": 4}, "session": {"2021-budget": 3}, "undated": 0}


class TopicRunOut(BaseModel):
    run_id: uuid.UUID | None
    built_at: datetime | None
    total_questions: int  # questions in parliament_questions right now
    topics: list[TopicOut]


class TopicQuestionOut(BaseModel):
    id: uuid.UUID
    house: House
    q_type: QuestionType
    q_no: str | None
    answer_date: date | None
    subject: str | None
    question_text: str
    document_id: uuid.UUID | None
    weight: float  # how strongly the question belongs to the topic
    keywords: list[str]


class RefreshOut(BaseModel):
    queued: bool
