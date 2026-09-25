"""PQ reply generator and report export (guide sections 10.1-10.3).

POST /pq-replies/draft     paste a PQ -> ParliamentQuestion + DRAFT pq_reply Report + citations
GET  /reports/{id}/export  DOCX or PDF in the official layout

The review workflow (edit, submit, approve, return, versions) is in app.api.reports. Nothing
here sends a reply anywhere: the draft is saved for an Analyst to edit and an Approver to
approve, and export only returns a file to the person who asked for it.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require, scope_to_user
from app.core.rbac import Permission
from app.llm.client import LlmUnavailable
from app.models import (
    Chunk,
    Document,
    Fact,
    ParliamentQuestion,
    Report,
    ReportCitation,
    ReportVersion,
    User,
)
from app.models.enums import ReportStatus, ReportType
from app.schemas.pq_reply import PqDraftIn, PqDraftOut
from app.services import audit, pq_reply, report_export

router = APIRouter(prefix="/pq-replies", tags=["pq-replies"])
export_router = APIRouter(prefix="/reports", tags=["reports"])


def report_title(body: PqDraftIn) -> str:
    house = pq_reply.HOUSE_LABEL[body.house].title()
    kind = body.q_type.value.title()
    subject = f": {body.subject.strip()}" if body.subject and body.subject.strip() else ""
    return f"{house} {kind} Q. No. {body.q_no or '-'}{subject}"[:500]


@router.post("/draft", response_model=PqDraftOut, status_code=status.HTTP_201_CREATED)
def create_draft(
    body: PqDraftIn,
    request: Request,
    user: User = Depends(require(Permission.EDIT_REPORTS)),
    db: Session = Depends(get_db),
) -> PqDraftOut:
    try:
        draft = pq_reply.draft_reply(
            db,
            user,
            house=body.house,
            q_type=body.q_type,
            q_no=body.q_no,
            answer_date=body.answer_date,
            mp_name=body.mp_name,
            subject=body.subject,
            question_text=body.question_text,
        )
    except LlmUnavailable as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"The local AI model is not available right now. ({e})",
        ) from None

    pq = ParliamentQuestion(
        house=body.house,
        q_type=body.q_type,
        q_no=body.q_no,
        answer_date=body.answer_date,
        mp_name=body.mp_name,
        subject=body.subject,
        question_text=body.question_text,
        parts_json=[{"label": p.label, "text": p.text} for p in draft.parts],
    )
    db.add(pq)
    db.flush()
    report = Report(
        report_type=ReportType.PQ_REPLY,
        title=report_title(body),
        status=ReportStatus.DRAFT,
        content_json=draft.content,
        pq_id=pq.id,
        org_unit_id=user.org_unit_id,
        created_by=user.id,
        due_date=body.answer_date,
    )
    db.add(report)
    db.flush()
    db.add(
        ReportVersion(
            report_id=report.id,
            version=1,
            content_json=draft.content,
            edited_by=user.id,
            change_note="First draft generated from the question",
        )
    )
    for link in draft.links:
        db.add(ReportCitation(report_id=report.id, **link))
    blocks = draft.content["blocks"]
    audit.record(
        db,
        "create_pq_draft",
        user_id=user.id,
        entity="report",
        entity_id=report.id,
        details={
            "pq_id": str(pq.id),
            "parts": len(blocks),
            "split_method": draft.split_method,
            "parts_not_found": sum(b["not_found"] for b in blocks),
            "sources": len(draft.content["sources"]),
        },
        request=request,
    )
    db.commit()
    db.refresh(report)
    return PqDraftOut(pq_id=pq.id, split_method=draft.split_method, report=report)


def _pq_header(db: Session, report: Report) -> dict | None:
    if report.pq_id is None:
        return None
    pq = db.get(ParliamentQuestion, report.pq_id)
    if pq is None:
        return None
    intro, _ = pq_reply.split_by_markers(pq.question_text)
    return pq_reply.build_header(
        house=pq.house,
        q_type=pq.q_type,
        q_no=pq.q_no,
        answer_date=pq.answer_date,
        mp_name=pq.mp_name,
        subject=pq.subject,
        intro=intro,
    )


def _db_sources(db: Session, report_id: uuid.UUID) -> list[dict]:
    """Sources from report_citations, for replies whose blocks were replaced by plain text."""
    rows = db.execute(
        select(ReportCitation, Document.title, Fact.page_no, Chunk.page_no)
        .outerjoin(Fact, Fact.id == ReportCitation.fact_id)
        .outerjoin(Chunk, Chunk.id == ReportCitation.chunk_id)
        .join(Document, Document.id == func.coalesce(Fact.document_id, Chunk.document_id))
        .where(ReportCitation.report_id == report_id)
        .order_by(ReportCitation.created_at)
    ).all()
    sources, seen = [], set()
    for cit, title, fact_page, chunk_page in rows:
        key = cit.fact_id or cit.chunk_id
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {"id": f"S{len(sources) + 1}", "document": title, "page": fact_page or chunk_page}
        )
    return sources


@export_router.get("/{report_id}/export")
def export_report(
    report_id: uuid.UUID,
    request: Request,
    format: Literal["docx", "pdf"] = Query("docx"),
    user: User = Depends(require(Permission.EXPORT_REPORTS)),
    db: Session = Depends(get_db),
) -> Response:
    report = db.scalar(scope_to_user(select(Report).where(Report.id == report_id), Report, user))
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    has_blocks = bool((report.content_json or {}).get("blocks"))
    view = report_export.view_from_report(
        report,
        _pq_header(db, report),
        [] if has_blocks else _db_sources(db, report.id),
    )
    if format == "pdf":
        data, mime = report_export.to_pdf(view), report_export.PDF_MIME
    else:
        data, mime = report_export.to_docx(view), report_export.DOCX_MIME
    audit.record(
        db,
        "export_report",
        user_id=user.id,
        entity="report",
        entity_id=report.id,
        details={"format": format, "status": report.status.value},
        request=request,
    )
    db.commit()
    name = f"{report.report_type.value.replace('_', '-')}-{str(report.id)[:8]}.{format}"
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
