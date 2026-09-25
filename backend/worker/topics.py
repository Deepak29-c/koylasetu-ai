"""Topic job (guide section 11, Module E). Runs on the "topics" queue, never in a request.

1. Fill parliament_questions from ingested PQ answer documents (doc_type pq_answer) that do
   not have a question row yet: the question, house, number and date are read from the text
   (app/services/pq_parse.py).
2. Re-build the topics when TOPICS_MIN_NEW_PQS new questions arrived since the last run (or
   always with force=True, which the admin "Re-run" button uses).

Queued after every processed pq_answer document (worker/ingest.py) and by
POST /topics/refresh. By hand:  python -m worker.topics [--force]
"""

from __future__ import annotations

import logging
import sys
import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import Chunk, Document, ParliamentQuestion, Topic
from app.models.enums import DocType, DocumentStatus
from app.services.pq_parse import parse_pq
from app.services.topics import TopicDoc, build_topics

log = logging.getLogger(__name__)

_DONE = (DocumentStatus.PROCESSED, DocumentStatus.NEEDS_REVIEW)


class _ChunkLike(Protocol):
    page_no: int
    bbox: list[float] | None
    text: str


def ordered_text(chunks: Iterable[_ChunkLike]) -> str:
    """Chunk texts in reading order (page, then top to bottom), joined by newlines."""

    def key(c: _ChunkLike) -> tuple:
        box = c.bbox or [0.0, float("inf")]
        return (c.page_no, box[1], box[0])

    return "\n".join(c.text for c in sorted(chunks, key=key))


def pq_text(pq: ParliamentQuestion) -> str:
    """What the topic model reads: the subject line plus the question itself."""
    return f"{pq.subject or ''}\n{pq.question_text}"


def sync_pqs_from_documents(db: Session) -> int:
    """Create a parliament_questions row for every processed PQ answer document without one.
    Returns the number of new questions."""
    linked = select(ParliamentQuestion.document_id).where(
        ParliamentQuestion.document_id.is_not(None)
    )
    docs = db.scalars(
        select(Document).where(
            Document.doc_type == DocType.PQ_ANSWER,
            Document.status.in_(_DONE),
            Document.id.not_in(linked),
        )
    ).all()
    added = 0
    for doc in docs:
        chunks = db.scalars(select(Chunk).where(Chunk.document_id == doc.id)).all()
        parsed = parse_pq(ordered_text(chunks))
        if parsed is None or parsed.house is None:
            log.info("Document %s: not a readable PQ answer, skipped", doc.id)
            continue
        if parsed.q_no and parsed.answer_date:
            same = db.scalar(
                select(ParliamentQuestion).where(
                    ParliamentQuestion.house == parsed.house,
                    ParliamentQuestion.q_no == parsed.q_no,
                    ParliamentQuestion.answer_date == parsed.answer_date,
                )
            )
            if same is not None:  # the same question uploaded twice (e.g. Hindi + English)
                same.document_id = same.document_id or doc.id
                continue
        db.add(
            ParliamentQuestion(
                house=parsed.house,
                q_type=parsed.q_type,
                q_no=parsed.q_no,
                answer_date=parsed.answer_date,
                mp_name="; ".join(parsed.mp_names)[:300] or None,
                subject=parsed.subject,
                question_text=parsed.question_text,
                answer_text=parsed.answer_text,
                parts_json=parsed.parts or None,
                document_id=doc.id,
            )
        )
        added += 1
    db.commit()
    return added


def latest_run(db: Session) -> tuple[uuid.UUID, datetime] | None:
    row = db.execute(
        select(Topic.run_id, Topic.created_at).order_by(Topic.created_at.desc()).limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def should_rebuild(new_pqs: int, has_run: bool, min_new: int, force: bool = False) -> bool:
    """Re-run rule (guide 11): first run, forced, or at least `min_new` new questions."""
    if force:
        return True
    if not has_run:
        return new_pqs > 0
    return new_pqs >= min_new


def rebuild_topics(db: Session) -> uuid.UUID | None:
    """Build topics over all past questions, save them as a new run, drop older runs."""
    pqs = db.scalars(select(ParliamentQuestion)).all()
    drafts = build_topics([TopicDoc(str(q.id), pq_text(q), q.answer_date) for q in pqs])
    if not drafts:
        log.info("Topics: not enough questions (%d) to build topics", len(pqs))
        return None
    run_id = uuid.uuid4()
    for d in drafts:
        db.add(
            Topic(
                run_id=run_id,
                topic_no=d.topic_no,
                label=d.label[:300],
                keywords=d.keywords,
                size=d.size,
                period_counts_json=d.period_counts,
                members_json=[
                    {"question_id": m.id, "weight": m.weight, "keywords": m.keywords}
                    for m in d.members
                ],
            )
        )
    db.execute(delete(Topic).where(Topic.run_id != run_id))
    db.commit()
    log.info("Topics: run %s, %d topics over %d questions", run_id, len(drafts), len(pqs))
    return run_id


def refresh_topics(force: bool = False) -> str | None:
    """RQ entry point. Returns the new run id, or None when nothing was re-built."""
    with SessionLocal() as db:
        added = sync_pqs_from_documents(db)
        run = latest_run(db)
        since = select(func.count(ParliamentQuestion.id))
        if run is not None:
            since = since.where(ParliamentQuestion.created_at > run[1])
        new_pqs = db.scalar(since) or 0
        log.info("Topics: %d questions read from documents, %d new since last run", added, new_pqs)
        if not should_rebuild(new_pqs, run is not None, get_settings().topics_min_new_pqs, force):
            return None
        run_id = rebuild_topics(db)
        return str(run_id) if run_id else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(refresh_topics(force="--force" in sys.argv))
