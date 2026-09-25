"""W1 ingestion job (guide section 7.1): detect, OCR, layout, tables, chunks, embeddings.

Run the worker with:  rq worker ingest topics reports

Status: UPLOADED -> PROCESSING -> PROCESSED | FAILED. Facts extraction and validation
(steps 10-11, NEEDS_REVIEW) are added in build step 3.
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import Chunk, Document, ExtractedTable, Page
from app.models.enums import DocumentStatus
from worker import parse
from worker.embed import chunk_blocks, embed_document
from worker.ocr import get_ocr

log = logging.getLogger(__name__)


def process_document(document_id: str) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, uuid.UUID(document_id))
        if doc is None:
            return
        doc.status = DocumentStatus.PROCESSING
        doc.pages_done = 0
        doc.error_message = None
        db.commit()

        try:
            run_pipeline(db, doc)
        except Exception as exc:
            db.rollback()
            doc.status = DocumentStatus.FAILED
            doc.error_message = f"{type(exc).__name__}: {exc}"[:2000]
            db.commit()
            raise


def run_pipeline(db, doc: Document) -> None:
    path = Path(doc.file_path)
    if not path.exists():
        raise FileNotFoundError(f"original file missing: {path}")

    # Retry-safe: remove results of any earlier run of this document.
    for model in (Chunk, ExtractedTable, Page):
        db.execute(delete(model).where(model.document_id == doc.id))
    doc.page_count = parse.page_count(path, doc.mime_type)
    db.commit()

    ocr = get_ocr(doc.language)
    total_chunks = 0
    for result in parse.parse(path, doc.mime_type, ocr):
        db.add(
            Page(
                document_id=doc.id,
                page_no=result.page_no,
                has_text_layer=result.has_text_layer,
                ocr_used=result.ocr_used,
                ocr_confidence=result.ocr_confidence,
            )
        )
        for table in result.tables:
            db.add(
                ExtractedTable(
                    document_id=doc.id,
                    page_no=result.page_no,
                    bbox=table.bbox,
                    rows_json=table.rows,
                    table_title=table.title,
                )
            )
        for draft in chunk_blocks(result.blocks):
            db.add(
                Chunk(document_id=doc.id, page_no=result.page_no, text=draft.text, bbox=draft.bbox)
            )
            total_chunks += 1
        doc.pages_done = result.page_no
        db.commit()  # one commit per page, so the Documents screen shows live progress

    embedded = embed_document(db, doc.id)
    if not embedded:
        log.info("Document %s: %d chunks saved without embeddings", doc.id, total_chunks)
    doc.status = DocumentStatus.PROCESSED
    db.commit()
