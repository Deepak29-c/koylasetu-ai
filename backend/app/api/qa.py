import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require
from app.core.rbac import Permission
from app.llm.client import LlmUnavailable
from app.models import QaLog, User
from app.schemas.qa import AskIn, AskOut, CitationOut, FeedbackIn
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
    return AskOut(
        qa_id=result.qa_id,
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
