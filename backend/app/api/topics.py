"""Topic explorer API (guide section 11): word cloud, topics, a topic's questions, re-run.

Past Parliament Questions are public records, so questions and topics are not org-scoped.
Document text in the word cloud (source=documents|all) is scoped to what the user may see.
Topics are built by the worker (worker/topics.py), never inside a request.
"""

import uuid
from collections import OrderedDict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require, scope_to_user, sees_all_units
from app.core.rbac import Permission
from app.models import Chunk, Document, OrgUnit, ParliamentQuestion, Topic, User
from app.models.enums import DocumentStatus, House
from app.schemas.topic import (
    RefreshOut,
    TopicOut,
    TopicQuestionOut,
    TopicRunOut,
    WordCloudOut,
)
from app.services import audit
from app.services.queue import enqueue_topics_refresh
from app.services.topics import fy_start_year, keep_question, word_cloud

router = APIRouter(prefix="/topics", tags=["topics"])

Session_ = Literal["budget", "monsoon", "winter"]
Source = Literal["questions", "documents", "all"]

MAX_DOC_CHUNKS = 20000  # enough for a word cloud; keeps one request bounded
_CACHE_SIZE = 64
# Word clouds cached by filter (guide 11). The key includes a data version (row counts and
# last update times), so new questions or documents show up without a manual flush.
_cache: OrderedDict[tuple, WordCloudOut] = OrderedDict()


def _cache_get(key: tuple) -> WordCloudOut | None:
    hit = _cache.get(key)
    if hit is not None:
        _cache.move_to_end(key)
    return hit


def _cache_put(key: tuple, value: WordCloudOut) -> None:
    _cache[key] = value
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)


def _question_texts(
    db: Session,
    house: House | None,
    year_from: int | None,
    year_to: int | None,
    session: str | None,
    subsidiary: str | None,
) -> list[str]:
    stmt = select(
        ParliamentQuestion.answer_date, ParliamentQuestion.subject, ParliamentQuestion.question_text
    )
    if house:
        stmt = stmt.where(ParliamentQuestion.house == house)
    year = extract("year", ParliamentQuestion.answer_date)
    if year_from:
        stmt = stmt.where(year >= year_from)
    if year_to:
        stmt = stmt.where(year <= year_to)
    texts = []
    for day, subject, question in db.execute(stmt):
        text = f"{subject or ''}\n{question}"
        if keep_question(day, text, session, subsidiary):
            texts.append(text)
    return texts


def _document_texts(
    db: Session, user: User, year_from: int | None, year_to: int | None, subsidiary: str | None
) -> list[str]:
    stmt = (
        select(Chunk.text, Document.fy)
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.status.in_((DocumentStatus.PROCESSED, DocumentStatus.NEEDS_REVIEW)))
    )
    stmt = scope_to_user(stmt, Document, user)
    if subsidiary:
        stmt = stmt.join(OrgUnit, Document.org_unit_id == OrgUnit.id).where(
            OrgUnit.code == subsidiary.upper()
        )
    texts = []
    for text, fy in db.execute(stmt.limit(MAX_DOC_CHUNKS)):
        start = fy_start_year(fy)
        if (year_from or year_to) and start is None:
            continue
        if year_from and start < year_from or year_to and start > year_to:
            continue
        texts.append(text)
    return texts


def _data_version(db: Session, source: str) -> tuple:
    version: tuple = ()
    if source in ("questions", "all"):
        version += tuple(
            db.execute(
                select(func.count(ParliamentQuestion.id), func.max(ParliamentQuestion.updated_at))
            ).one()
        )
    if source in ("documents", "all"):
        version += tuple(
            db.execute(select(func.count(Document.id), func.max(Document.updated_at))).one()
        )
    return version


@router.get("/wordcloud", response_model=WordCloudOut)
def get_wordcloud(
    house: House | None = None,
    year_from: int | None = Query(None, alias="from", ge=1950, le=2100),
    year_to: int | None = Query(None, alias="to", ge=1950, le=2100),
    session: Session_ | None = None,
    subsidiary: str | None = Query(None, max_length=16),
    source: Source = "questions",
    limit: int = Query(80, ge=10, le=200),
    user: User = Depends(require(Permission.VIEW_TOPICS)),
    db: Session = Depends(get_db),
) -> WordCloudOut:
    """Most frequent words, e.g. /topics/wordcloud?house=LS&from=2019&to=2025.

    house / session apply to questions only; from / to use the answer date for questions
    and the financial year for documents.
    """
    if year_from and year_to and year_from > year_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "'from' is after 'to'")
    scope = None
    if source != "questions" and not sees_all_units(user):
        scope = str(user.org_unit_id)
    key = (house, year_from, year_to, session, subsidiary, source, limit, scope)
    key += _data_version(db, source)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    texts: list[str] = []
    if source in ("questions", "all"):
        texts += _question_texts(db, house, year_from, year_to, session, subsidiary)
    if source in ("documents", "all"):
        texts += _document_texts(db, user, year_from, year_to, subsidiary)
    result = WordCloudOut(source=source, texts=len(texts), words=word_cloud(texts, limit))
    _cache_put(key, result)
    return result


@router.get("", response_model=TopicRunOut)
def list_topics(
    user: User = Depends(require(Permission.VIEW_TOPICS)),
    db: Session = Depends(get_db),
) -> TopicRunOut:
    """Topics of the latest run, largest first, with counts per year and session."""
    total = db.scalar(select(func.count(ParliamentQuestion.id))) or 0
    latest = db.scalar(select(Topic).order_by(Topic.created_at.desc()).limit(1))
    if latest is None:
        return TopicRunOut(run_id=None, built_at=None, total_questions=total, topics=[])
    topics = db.scalars(
        select(Topic).where(Topic.run_id == latest.run_id).order_by(Topic.topic_no)
    ).all()
    return TopicRunOut(
        run_id=latest.run_id,
        built_at=latest.created_at,
        total_questions=total,
        topics=[
            TopicOut(
                id=t.id,
                topic_no=t.topic_no,
                label=t.label,
                keywords=t.keywords,
                size=t.size,
                period_counts=t.period_counts_json or {},
            )
            for t in topics
        ],
    )


@router.get("/{topic_id}/questions", response_model=list[TopicQuestionOut])
def topic_questions(
    topic_id: uuid.UUID,
    year: int | None = Query(None, ge=1950, le=2100),
    user: User = Depends(require(Permission.VIEW_TOPICS)),
    db: Session = Depends(get_db),
) -> list[TopicQuestionOut]:
    """The topic's questions, the most typical first. `year` narrows to one answer year."""
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    members = topic.members_json or []
    ids = [uuid.UUID(m["question_id"]) for m in members]
    pqs = {
        q.id: q
        for q in db.scalars(select(ParliamentQuestion).where(ParliamentQuestion.id.in_(ids)))
    }
    out = []
    for m in members:
        q = pqs.get(uuid.UUID(m["question_id"]))
        if q is None or (year and (q.answer_date is None or q.answer_date.year != year)):
            continue
        out.append(
            TopicQuestionOut(
                id=q.id,
                house=q.house,
                q_type=q.q_type,
                q_no=q.q_no,
                answer_date=q.answer_date,
                subject=q.subject,
                question_text=q.question_text,
                document_id=q.document_id,
                weight=m.get("weight", 0.0),
                keywords=m.get("keywords", []),
            )
        )
    return out


@router.post("/refresh", response_model=RefreshOut)
def refresh(
    request: Request,
    user: User = Depends(require(Permission.MANAGE_ADMIN)),
    db: Session = Depends(get_db),
) -> RefreshOut:
    """Admin: queue a full re-run now (read new PQ documents, re-build topics)."""
    queued = enqueue_topics_refresh(force=True)
    audit.record(
        db,
        "topics_refresh",
        actor=user,
        entity="topics",
        details={"queued": queued},
        request=request,
    )
    db.commit()
    return RefreshOut(queued=queued)
