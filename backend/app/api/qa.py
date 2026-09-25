import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require
from app.core.rbac import Permission
from app.llm.client import LlmUnavailable
from app.models import QaLog, User
from app.schemas.qa import AskIn, AskOut, CitationOut, FeedbackIn, QaHistoryOut
from app.services import qa
from app.services.facts_query import FactRow

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask", response_model=AskOut)
def ask(
    body: AskIn,
    user: User = Depends(require(Permission.ASK_QUESTIONS)),
    db: Session = Depends(get_db),
) -> AskOut:
    try:
        result = qa.ask(db, user, body.question)
    except LlmUnavailable as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"The local AI model is not available right now. ({e})",
        ) from None
    return _answer_out(result)


def _answer_out(result: qa.Answer, question: str | None = None) -> AskOut:
    return AskOut(
        qa_id=result.qa_id,
        question=question,
        answer=result.answer,
        route=result.route,
        table=result.table,
        citations=[_citation(c) for c in result.citations],
        grounded=result.grounded,
        unmatched_numbers=result.unmatched_numbers,
        confidence=result.confidence,
        not_found=result.not_found,
        latency_ms=result.latency_ms,
    )


# Declared before /{qa_id} so "history" is not read as an id.
@router.get("/history", response_model=list[QaHistoryOut])
def history(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require(Permission.ASK_QUESTIONS)),
    db: Session = Depends(get_db),
) -> list[QaLog]:
    """Questions this person asked, newest first. Only ever their own."""
    stmt = (
        select(QaLog).where(QaLog.user_id == user.id).order_by(QaLog.created_at.desc()).limit(limit)
    )
    return list(db.scalars(stmt))


@router.get("/{qa_id}", response_model=AskOut)
def get_answer(
    qa_id: uuid.UUID,
    user: User = Depends(require(Permission.ASK_QUESTIONS)),
    db: Session = Depends(get_db),
) -> AskOut:
    """A past answer, rebuilt - so opening a source and coming back is not a dead end.

    Nothing is re-asked and the model is not called: the stored answer is returned with
    its sources read back from the database, scoped to this user.
    """
    log = db.get(QaLog, qa_id)
    if log is None or log.user_id != user.id:  # people reopen only their own answers
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found")
    return _answer_out(qa.replay(db, log, user), question=log.question)


def _citation(c: qa.Source) -> CitationOut:
    common = {
        "id": c.ref,
        "document_id": c.document_id,
        "document": c.document_title,
        "page": c.page_no,
        "bbox": c.bbox,
    }
    if isinstance(c, FactRow):
        return CitationOut(
            **common, kind="fact", fact_id=c.fact_id, status=c.status, text=qa.fact_line(c)
        )
    return CitationOut(**common, kind="passage", chunk_id=c.chunk_id, text=c.text)


@router.post("/{qa_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def feedback(
    qa_id: uuid.UUID,
    body: FeedbackIn,
    user: User = Depends(require(Permission.ASK_QUESTIONS)),
    db: Session = Depends(get_db),
) -> None:
    log = db.get(QaLog, qa_id)
    if log is None or log.user_id != user.id:  # users rate only their own answers
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found")
    log.feedback = body.model_dump()
    db.commit()
