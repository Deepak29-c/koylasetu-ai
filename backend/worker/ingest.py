"""W1 ingestion job (guide section 7.1): detect, OCR, layout, tables, then chunk/embed/extract.

Run the worker with:  rq worker ingest topics reports
"""

import uuid

from app.core.db import SessionLocal
from app.models import Document
from app.models.enums import DocumentStatus


def process_document(document_id: str) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, uuid.UUID(document_id))
        if doc is None:
            return
        doc.status = DocumentStatus.PROCESSING
        doc.pages_done = 0
        db.commit()

        try:
            run_pipeline(doc)
        except Exception as exc:
            db.rollback()
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(exc)[:2000]
            db.commit()
            raise


def run_pipeline(doc: Document) -> None:
    # Steps 1-11 of guide 7.1 go here (store is already done by the API).
    raise NotImplementedError("Ingestion pipeline is not built yet (build step 1 / W1)")
