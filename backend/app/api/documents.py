import io
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
from app.services import audit, file_types, storage
from app.services.normalise import normalise_fy
from app.services.queue import enqueue_ingest

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
    user: User = Depends(require(Permission.UPLOAD_DOCUMENTS)),
    db: Session = Depends(get_db),
) -> list[UploadResult]:
    """Upload one or many files. Each file gets its own result (created / duplicate / rejected)."""
    if is_public and not (sees_all_units(user) or Role.ADMIN in user.roles):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only CIL HQ, Ministry or Admin can mark documents public"
        )
    try:
        fy = normalise_fy(fy)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None

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

        existing = db.scalar(select(Document).where(Document.sha256 == tmp.sha256))
        if existing is not None:
            tmp.path.unlink(missing_ok=True)
            visible = db.scalar(
                scope_to_user(select(Document).where(Document.id == existing.id), Document, user)
            )
            results.append(
                UploadResult(
                    filename=name,
                    result="duplicate",
                    document=DocumentOut.model_validate(visible) if visible else None,
                    error="This exact file was uploaded before",
                )
            )
            continue

        path = storage.move_to_originals(tmp, kind.ext)
        doc = Document(
            title=Path(name).stem,
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
            user_id=user.id,
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


def _page_size(doc: Document, page_no: int) -> tuple[float | None, float | None]:
    path = Path(doc.file_path)
    if doc.mime_type == "application/pdf":
        with pymupdf.open(path) as pdf:
            rect = pdf[page_no - 1].rect
            return rect.width, rect.height
    if doc.mime_type.startswith("image/"):
        with Image.open(path) as img:
            img.seek(page_no - 1)
            return float(img.width), float(img.height)
    return None, None


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
    path = Path(doc.file_path)
    if doc.mime_type == "application/pdf":
        with pymupdf.open(path) as pdf:
            png = pdf[page_no - 1].get_pixmap(dpi=dpi).tobytes("png")
    elif doc.mime_type.startswith("image/"):
        with Image.open(path) as img:
            img.seek(page_no - 1)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "PNG")
            png = buf.getvalue()
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This file type has no page images")
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
    audit.record(db, "retry", user_id=user.id, entity="document", entity_id=doc.id, request=request)
    db.commit()
    queued = enqueue_ingest(doc.id)
    return UploadResult(
        filename=doc.original_filename,
        result="created",
        document=DocumentOut.model_validate(doc),
        queued=queued,
    )
