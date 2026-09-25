"""PQ reply generator and report export (guide sections 10.1-10.3).

POST /pq-replies/draft          paste a PQ -> ParliamentQuestion + DRAFT pq_reply Report + citations
POST /pq-replies/parts          the parts (a), (b)… the question splits into, before generating
POST /pq-replies/question-text  the plain text of a PQ file (PDF, Word, text), to fill the form
GET  /reports/{id}/export       DOCX or PDF in the official layout

The review workflow (edit, submit, approve, return, versions) is in app.api.reports. Nothing
here sends a reply anywhere: the draft is saved for an Analyst to edit and an Approver to
approve, and export only returns a file to the person who asked for it.
"""

import logging
import uuid
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import require, scope_to_user
from app.core.errors import CodedError
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
from app.models.enums import ReportChangeKind, ReportStatus, ReportType
from app.schemas.pq_reply import (
    PqDraftIn,
    PqDraftOut,
    PqPartOut,
    PqPartsIn,
    PqPartsOut,
    PqQuestionTextOut,
)
from app.services import audit, pq_reply, question_file, report_export, storage

log = logging.getLogger(__name__)

router = APIRouter(prefix="/pq-replies", tags=["pq-replies"])
export_router = APIRouter(prefix="/reports", tags=["reports"])

MODEL_DOWN = (
    "The local AI model is not available right now, so no draft was made. "
    "Please try again later or ask the administrator to check the model server."
)


def report_title(body: PqDraftIn) -> str:
    house = pq_reply.HOUSE_LABEL[body.house].title()
    kind = body.q_type.value.title()
    subject = f": {body.subject.strip()}" if body.subject and body.subject.strip() else ""
    return f"{house} {kind} Q. No. {body.q_no or '-'}{subject}"[:500]


def _same_request(db: Session, user: User, key: str | None) -> Report | None:
    """The report already made for this Idempotency-Key by this user, if any. Generation takes
    minutes, so a browser or proxy retry must not create a second PQ + report."""
    if not key:
        return None
    return db.scalar(
        select(Report).where(
            Report.created_by == user.id,
            Report.content_json["idempotency_key"].astext == key,
        )
    )


def _out(report: Report) -> PqDraftOut:
    return PqDraftOut(
        pq_id=report.pq_id,
        split_method=report.content_json.get("split_method", "markers"),
        report=report,
    )


@router.post("/draft", response_model=PqDraftOut, status_code=status.HTTP_201_CREATED)
def create_draft(
    body: PqDraftIn,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, max_length=64),
    user: User = Depends(require(Permission.EDIT_REPORTS)),
    db: Session = Depends(get_db),
) -> PqDraftOut:
    existing = _same_request(db, user, idempotency_key)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _out(existing)
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
        log.warning("PQ draft failed, model unavailable: %s", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MODEL_DOWN) from None
    # A retry with the same key may have finished while this one was generating.
    existing = _same_request(db, user, idempotency_key)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _out(existing)

    content = draft.content | {"split_method": draft.split_method}
    if idempotency_key:
        content["idempotency_key"] = idempotency_key
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
        content_json=content,
        pq_id=pq.id,
        org_unit_id=user.org_unit_id,
        created_by=user.id,
        due_date=body.due_date or body.answer_date,
    )
    db.add(report)
    db.flush()
    db.add(
        ReportVersion(
            report_id=report.id,
            version=1,
            content_json=content,
            edited_by=user.id,
            change_kind=ReportChangeKind.DRAFTED_FROM_QUESTION,
        )
    )
    for link in draft.links:
        db.add(ReportCitation(report_id=report.id, **link))
    blocks = content["blocks"]
    audit.record(
        db,
        "create_pq_draft",
        actor=user,
        entity="report",
        entity_id=report.id,
        details={
            "pq_id": str(pq.id),
            "parts": len(blocks),
            "split_method": draft.split_method,
            "parts_not_found": sum(b["not_found"] for b in blocks),
            "figures_removed": sum(len(b["removed_numbers"]) for b in blocks),
            "sources": len(content["sources"]),
        },
        request=request,
    )
    db.commit()
    db.refresh(report)
    return _out(report)


@router.post("/parts", response_model=PqPartsOut)
def preview_parts(
    body: PqPartsIn,
    _user: User = Depends(require(Permission.EDIT_REPORTS)),
) -> PqPartsOut:
    """The parts the question splits into on its own markers, shown under the question box
    while it is typed. The model is not asked here; with no markers, generation may still
    split the question with the model, or answer it as one."""
    intro, parts = pq_reply.split_by_markers(body.question_text)
    return PqPartsOut(
        method="markers" if parts else "single",
        intro=intro if parts else "",
        parts=[PqPartOut(part=p.label, text=p.text) for p in parts],
        max_parts=pq_reply.MAX_PARTS,
    )


@router.post("/question-text", response_model=PqQuestionTextOut)
async def question_text(
    file: UploadFile = File(...),
    _user: User = Depends(require(Permission.EDIT_REPORTS)),
) -> PqQuestionTextOut:
    """Read the question out of a PDF, Word or text file. The file is not kept."""
    name = file.filename or "upload"
    try:
        tmp = await storage.save_temp(file)
    except storage.FileTooLarge:
        limit = get_settings().max_upload_mb
        raise CodedError(
            status.HTTP_413_CONTENT_TOO_LARGE, "pq_file_too_large", f"Larger than {limit} MB"
        ) from None
    try:
        text, truncated = question_file.read_question(tmp.path, name)
    except question_file.NotAllowed:
        raise CodedError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "pq_file_type",
            "Not an allowed file type for a question (PDF, Word DOCX or a .txt text file)",
        ) from None
    except question_file.Unreadable:
        raise CodedError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "pq_file_unreadable",
            "The file could not be opened. It may be damaged or password-protected.",
        ) from None
    except question_file.NoText:
        raise CodedError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "pq_file_no_text",
            "No text was found in the file. A scanned PDF has no text layer; "
            "paste the question instead.",
        ) from None
    finally:
        tmp.path.unlink(missing_ok=True)
    return PqQuestionTextOut(filename=name, text=text, truncated=truncated)


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
    """Sources from report_citations, for replies whose blocks were replaced by plain text,
    numbered as in the text (the S-number is kept in location_in_report)."""
    rows = db.execute(
        select(
            ReportCitation.location_in_report,
            func.coalesce(ReportCitation.fact_id, ReportCitation.chunk_id),
            Document.title,
            func.coalesce(Fact.page_no, Chunk.page_no),
        )
        .outerjoin(Fact, Fact.id == ReportCitation.fact_id)
        .outerjoin(Chunk, Chunk.id == ReportCitation.chunk_id)
        .join(Document, Document.id == func.coalesce(Fact.document_id, Chunk.document_id))
        .where(ReportCitation.report_id == report_id)
    ).all()
    return pq_reply.sources_from_links([tuple(r) for r in rows])


def status_after_export(current: ReportStatus) -> ReportStatus:
    """ReportStatus.EXPORTED existed but nothing could ever set it - this is what does.

    Only an approved report becomes EXPORTED. Exporting a draft is a preview and should
    not look like the end of the workflow, and re-exporting leaves the status alone.
    """
    return ReportStatus.EXPORTED if current == ReportStatus.APPROVED else current


def export_statement(report_id: uuid.UUID, user: User):
    """The org-scoped query for the report to export (a user outside the unit gets a 404)."""
    return scope_to_user(select(Report).where(Report.id == report_id), Report, user)


@export_router.get("/{report_id}/export")
def export_report(
    report_id: uuid.UUID,
    request: Request,
    format: Literal["docx", "pdf"] = Query("docx"),
    user: User = Depends(require(Permission.EXPORT_REPORTS)),
    db: Session = Depends(get_db),
) -> Response:
    report = db.scalar(export_statement(report_id, user))
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    content = report.content_json or {}
    has_blocks = bool(content.get("blocks")) and bool(content.get("header"))
    items = report_export.items_for_report(
        report,
        _pq_header(db, report),
        [] if has_blocks else _db_sources(db, report.id),
    )
    if format == "pdf":
        data, mime = report_export.to_pdf(items), report_export.PDF_MIME
    else:
        data, mime = report_export.to_docx(items), report_export.DOCX_MIME
    was = report.status
    report.status = status_after_export(was)
    audit.record(
        db,
        "export_report",
        actor=user,
        entity="report",
        entity_id=report.id,
        details={"format": format, "status": was.value},
        request=request,
    )
    db.commit()
    name = f"{report.report_type.value.replace('_', '-')}-{str(report.id)[:8]}.{format}"
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
