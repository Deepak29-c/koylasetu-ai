import io
import logging
import uuid
from pathlib import Path

import pymupdf
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from PIL import Image
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import require, scope_to_user, sees_all_units
from app.core.errors import CodedError
from app.core.rbac import Permission, Role
from app.models import Chunk, Document, ExtractedTable, Fact, Page, ReviewActionLog, User
from app.models.enums import DocType, DocumentStatus, Metric
from app.schemas.document import (
    ChunkOut,
    DocumentOut,
    FactOut,
    PageOut,
    TableOut,
    UploadResult,
)
from app.services import audit, failures, file_types, storage
from app.services.normalise import normalise_fy
from app.services.queue import enqueue_ingest

log = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=list[UploadResult])
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    doc_type: DocType = Form(...),
    fy: str | None = Form(None),
    language: str = Form("en"),
    is_public: bool = Form(False),
    source_url: str | None = Form(None),
    title: str | None = Form(None),
    user: User = Depends(require(Permission.UPLOAD_DOCUMENTS)),
    db: Session = Depends(get_db),
) -> list[UploadResult]:
    """Upload one or many files. Each file gets its own result (created / duplicate / rejected).

    `title` is optional and only allowed for a single file (e.g. the bulk loader sends the
    official title from data/sources.csv); otherwise the title is the file name.
    """
    if is_public and not (sees_all_units(user) or Role.ADMIN in user.roles):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only CIL HQ, Ministry or Admin can mark documents public"
        )
    try:
        fy = normalise_fy(fy)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    title = " ".join(title.split()) if title else None
    if title and (len(files) != 1 or len(title) > 500):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "A title can only be given for a single file, up to 500 characters",
        )

    results: list[UploadResult] = []
    for upload in files:
        name = upload.filename or "upload"
        try:
            tmp = await storage.save_temp(upload)
        except storage.FileTooLarge:
            limit = get_settings().max_upload_mb
            results.append(
                UploadResult(filename=name, result="rejected", error=f"Larger than {limit} MB")
            )
            continue

        with tmp.path.open("rb") as fh:
            kind = file_types.detect(fh.read(8192), name, fh)
        if kind is None:
            tmp.path.unlink(missing_ok=True)
            results.append(
                UploadResult(
                    filename=name,
                    result="rejected",
                    error="Not an allowed file type (PDF, XLSX/XLS/CSV, PNG/JPG/TIFF, DOCX)",
                )
            )
            continue

        # Only a copy this person can actually open counts as a duplicate: their own
        # unit's, or one shared publicly. Another unit's private copy is not their
        # document, so they get their own - previously that was a dead end (#44).
        visible = db.scalar(
            scope_to_user(select(Document).where(Document.sha256 == tmp.sha256), Document, user)
        )
        if visible is not None:
            tmp.path.unlink(missing_ok=True)
            results.append(
                UploadResult(
                    filename=name,
                    result="duplicate",
                    document=DocumentOut.model_validate(visible),
                    error="This file is already here - opening it instead of adding it again",
                )
            )
            continue

        path = storage.move_to_originals(tmp, kind.ext)
        doc = Document(
            title=title or Path(name).stem,
            original_filename=name,
            doc_type=doc_type,
            fy=fy,
            org_unit_id=user.org_unit_id,
            is_public=is_public,
            language=language,
            file_path=str(path),
            mime_type=kind.mime,
            size_bytes=tmp.size,
            sha256=tmp.sha256,
            status=DocumentStatus.UPLOADED,
            uploaded_by=user.id,
            source_url=source_url,
        )
        db.add(doc)
        db.flush()
        audit.record(
            db,
            "upload",
            actor=user,
            entity="document",
            entity_id=doc.id,
            details={"filename": name, "sha256": tmp.sha256},
            request=request,
        )
        db.commit()
        queued = enqueue_ingest(doc.id)
        results.append(
            UploadResult(
                filename=name,
                result="created",
                document=DocumentOut.model_validate(doc),
                queued=queued,
            )
        )
    return results


@router.get("", response_model=list[DocumentOut])
def list_documents(
    status_filter: DocumentStatus | None = Query(None, alias="status"),
    user: User = Depends(require(Permission.VIEW_PROCESSING)),
    db: Session = Depends(get_db),
) -> list[Document]:
    stmt = scope_to_user(select(Document), Document, user).order_by(Document.created_at.desc())
    if status_filter:
        stmt = stmt.where(Document.status == status_filter)
    return list(db.scalars(stmt.limit(500)))


def _get_scoped(db: Session, document_id: uuid.UUID, user: User) -> Document:
    doc = db.scalar(
        scope_to_user(select(Document).where(Document.id == document_id), Document, user)
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    user: User = Depends(require(Permission.VIEW_PROCESSING)),
    db: Session = Depends(get_db),
) -> Document:
    return _get_scoped(db, document_id, user)


def _original(doc: Document) -> Path:
    """The document's original file, or a handled 404 naming the document when it is gone
    (#69). Unhandled, the missing file used to surface as a 500 without CORS headers, which
    the browser reported as "cannot reach the server"."""
    if failures.original_is_missing(doc.file_path):
        log.warning("Document %s: original file missing at %s", doc.id, doc.file_path)
        raise CodedError(
            status.HTTP_404_NOT_FOUND,
            "file_missing",
            f'The original file for "{doc.title}" could not be found on the server. '
            "Please upload it again.",
        )
    return Path(doc.file_path)


def _unreadable(doc: Document, exc: Exception) -> CodedError:
    """A 422 for an original that exists but cannot be opened; the detail goes to the log."""
    log.warning("Document %s: original file unreadable: %r", doc.id, exc)
    return CodedError(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "damaged_file",
        f'The original file for "{doc.title}" is damaged or could not be opened. '
        "Please upload a fresh copy.",
    )


def _page_size(doc: Document, page_no: int) -> tuple[float | None, float | None]:
    if doc.mime_type != "application/pdf" and not doc.mime_type.startswith("image/"):
        return None, None
    path = _original(doc)
    try:
        if doc.mime_type == "application/pdf":
            with pymupdf.open(path) as pdf:
                rect = pdf[page_no - 1].rect
                return rect.width, rect.height
        with Image.open(path) as img:
            img.seek(page_no - 1)
            return float(img.width), float(img.height)
    except Exception as exc:  # corrupt file, wrong format, page no longer there
        raise _unreadable(doc, exc) from None


@router.get("/{document_id}/pages/{page_no}", response_model=PageOut)
def get_page(
    document_id: uuid.UUID,
    page_no: int,
    user: User = Depends(require(Permission.ASK_QUESTIONS)),
    db: Session = Depends(get_db),
) -> PageOut:
    """Page text chunks + tables with their boxes, for highlighting in the viewer."""
    doc = _get_scoped(db, document_id, user)
    page = db.scalar(select(Page).where(Page.document_id == doc.id, Page.page_no == page_no))
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not processed")
    chunks = db.scalars(
        select(Chunk).where(Chunk.document_id == doc.id, Chunk.page_no == page_no)
    ).all()
    tables = db.scalars(
        select(ExtractedTable).where(
            ExtractedTable.document_id == doc.id, ExtractedTable.page_no == page_no
        )
    ).all()
    width, height = _page_size(doc, page_no)
    renderable = doc.mime_type == "application/pdf" or doc.mime_type.startswith("image/")
    return PageOut(
        document_id=doc.id,
        document_title=doc.title,
        source_url=doc.source_url,
        page_no=page_no,
        page_count=doc.page_count,
        has_text_layer=page.has_text_layer,
        ocr_used=page.ocr_used,
        ocr_confidence=page.ocr_confidence,
        width=width,
        height=height,
        image_url=f"/documents/{doc.id}/pages/{page_no}/image" if renderable else None,
        chunks=[
            ChunkOut(id=c.id, text=c.text, bbox=c.bbox, has_embedding=c.embedding is not None)
            for c in chunks
        ],
        tables=[TableOut.model_validate(t) for t in tables],
    )


@router.get("/{document_id}/facts", response_model=list[FactOut])
def list_facts(
    document_id: uuid.UUID,
    page_no: int | None = Query(None, ge=1),
    metric: Metric | None = None,
    user: User = Depends(require(Permission.VIEW_PROCESSING)),
    db: Session = Depends(get_db),
) -> list[Fact]:
    """Numbers extracted from this document's tables, each with its page and cell box."""
    doc = _get_scoped(db, document_id, user)
    stmt = select(Fact).where(Fact.document_id == doc.id)
    if page_no is not None:
        stmt = stmt.where(Fact.page_no == page_no)
    if metric is not None:
        stmt = stmt.where(Fact.metric == metric)
    return list(db.scalars(stmt.order_by(Fact.page_no, Fact.metric, Fact.subsidiary).limit(5000)))


@router.get("/{document_id}/pages/{page_no}/image", response_class=Response)
def get_page_image(
    document_id: uuid.UUID,
    page_no: int,
    dpi: int = Query(110, ge=50, le=200),
    user: User = Depends(require(Permission.ASK_QUESTIONS)),
    db: Session = Depends(get_db),
) -> Response:
    """PNG of the page, rendered on demand from the original file."""
    doc = _get_scoped(db, document_id, user)
    if not doc.page_count or not 1 <= page_no <= doc.page_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such page")
    if doc.mime_type != "application/pdf" and not doc.mime_type.startswith("image/"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This file type has no page images")
    path = _original(doc)
    try:
        if doc.mime_type == "application/pdf":
            with pymupdf.open(path) as pdf:
                png = pdf[page_no - 1].get_pixmap(dpi=dpi).tobytes("png")
        else:
            with Image.open(path) as img:
                img.seek(page_no - 1)
                buf = io.BytesIO()
                img.convert("RGB").save(buf, "PNG")
                png = buf.getvalue()
    except Exception as exc:  # corrupt file, wrong format, page no longer there
        raise _unreadable(doc, exc) from None
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/{document_id}/retry", response_model=UploadResult)
def retry_document(
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(require(Permission.UPLOAD_DOCUMENTS)),
    db: Session = Depends(get_db),
) -> UploadResult:
    doc = _get_scoped(db, document_id, user)
    # Any finished document can be re-run (e.g. after an OCR improvement); the pipeline
    # clears its earlier results first. Only a document being processed right now is blocked.
    if doc.status == DocumentStatus.PROCESSING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Document is being processed right now")
    reviewed = db.scalar(
        select(exists().where(ReviewActionLog.fact_id == Fact.id, Fact.document_id == doc.id))
    )
    if reviewed:
        # Re-processing replaces the document's facts; never silently discard human decisions.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A reviewer has already checked figures from this document; it can't be re-processed",
        )
    doc.status, doc.error_message, doc.pages_done = DocumentStatus.UPLOADED, None, 0
    audit.record(db, "retry", actor=user, entity="document", entity_id=doc.id, request=request)
    db.commit()
    queued = enqueue_ingest(doc.id)
    return UploadResult(
        filename=doc.original_filename,
        result="created",
        document=DocumentOut.model_validate(doc),
        queued=queued,
    )
