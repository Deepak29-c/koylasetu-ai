import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import require, scope_to_user, sees_all_units
from app.core.rbac import Permission, Role
from app.models import Document, User
from app.models.enums import DocType, DocumentStatus
from app.schemas.document import DocumentOut, UploadResult
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


@router.post("/{document_id}/retry", response_model=UploadResult)
def retry_document(
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(require(Permission.UPLOAD_DOCUMENTS)),
    db: Session = Depends(get_db),
) -> UploadResult:
    doc = _get_scoped(db, document_id, user)
    if doc.status not in (DocumentStatus.FAILED, DocumentStatus.UPLOADED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Document is {doc.status}, not FAILED")
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
