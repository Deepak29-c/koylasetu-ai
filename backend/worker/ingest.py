"""W1 ingestion job (guide section 7.1): detect, OCR, layout, tables, facts, chunks, embeddings.

Run the worker with:  rq worker ingest topics reports

Status: UPLOADED -> PROCESSING -> PROCESSED | FAILED. Validation (step 11, NEEDS_REVIEW) is
added with the validation rules.
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models import Chunk, Document, ExtractedTable, Fact, Page
from app.models.enums import DocumentStatus
from worker import parse
from worker.embed import embed_document, page_chunks
from worker.extract import extract_table, llm_classifier
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
    for model in (Fact, Chunk, ExtractedTable, Page):
        db.execute(delete(model).where(model.document_id == doc.id))
    doc.page_count = parse.page_count(path, doc.mime_type)
    db.commit()

    ocr = get_ocr(doc.language)
    classify = llm_classifier()
    total_chunks = total_facts = 0
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
            saved = ExtractedTable(
                document_id=doc.id,
                page_no=result.page_no,
                bbox=table.bbox,
                rows_json=table.rows,
                cell_bboxes=table.cell_bboxes,
                table_title=table.title,
            )
            db.add(saved)
            db.flush()  # facts point at the table's id
            total_facts += extract_table(db, doc.id, saved, result.ocr_confidence, classify)
        for draft in page_chunks(result):
            db.add(
                Chunk(document_id=doc.id, page_no=result.page_no, text=draft.text, bbox=draft.bbox)
            )
            total_chunks += 1
        doc.pages_done = result.page_no
        db.commit()  # one commit per page, so the Documents screen shows live progress

    log.info("Document %s: %d facts from tables", doc.id, total_facts)
    embedded = embed_document(db, doc.id)
    if not embedded:
        log.info("Document %s: %d chunks saved without embeddings", doc.id, total_chunks)
    doc.status = DocumentStatus.PROCESSED
    db.commit()
