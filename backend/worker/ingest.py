"""W1 ingestion job (guide section 7.1): detect, OCR, layout, tables, chunks, embeddings.

Run the worker with:  rq worker ingest topics reports

Status: UPLOADED -> PROCESSING -> PROCESSED | FAILED. Facts extraction and validation
(steps 10-11, NEEDS_REVIEW) are added in build step 3.
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models import Chunk, Document, ExtractedTable, Fact, Page, ValidationIssue
from app.models.enums import DocumentStatus, FactStatus
from worker import parse
from worker.embed import embed_document, page_chunks
from worker.extract import FactDraft, extract_facts
from worker.ocr import get_ocr
from worker.validate import Other, validate

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

    # Retry-safe: remove results of any earlier run of this document. (The API refuses a
    # re-run once a reviewer has acted on its facts, so no human decision is lost here.)
    for model in (Fact, Chunk, ExtractedTable, Page):
        db.execute(delete(model).where(model.document_id == doc.id))
    doc.page_count = parse.page_count(path, doc.mime_type)
    db.commit()

    ocr = get_ocr(doc.language)
    total_chunks = 0
    drafts: list[tuple[FactDraft, uuid.UUID]] = []
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
        context = f"{doc.title} " + " ".join(b.text for b in result.blocks)
        # guide 7.4: 1.0 for digital text, the page's OCR confidence for scanned pages
        cell_confidence = (result.ocr_confidence or 0.0) if result.ocr_used else 1.0
        for table in result.tables:
            stored = ExtractedTable(
                document_id=doc.id,
                page_no=result.page_no,
                bbox=table.bbox,
                rows_json=table.rows,
                table_title=table.title,
            )
            db.add(stored)
            db.flush()
            for draft in extract_facts(table, result.page_no, context, doc.fy, cell_confidence):
                drafts.append((draft, stored.id))
        for draft in page_chunks(result):
            db.add(
                Chunk(document_id=doc.id, page_no=result.page_no, text=draft.text, bbox=draft.bbox)
            )
            total_chunks += 1
        doc.pages_done = result.page_no
        db.commit()  # one commit per page, so the Documents screen shows live progress

    open_issues = store_facts(db, doc, drafts)
    embedded = embed_document(db, doc.id)
    if not embedded:
        log.info("Document %s: %d chunks saved without embeddings", doc.id, total_chunks)
    doc.status = DocumentStatus.NEEDS_REVIEW if open_issues else DocumentStatus.PROCESSED
    db.commit()


def store_facts(db, doc: Document, drafts: list[tuple[FactDraft, uuid.UUID]]) -> int:
    """Validate the document's facts (guide 8), save them and their issues. Returns the number
    of issues. Facts with no issue are accepted automatically (VERIFIED); the rest are FLAGGED
    for the Reviewer."""
    if not drafts:
        return 0
    metrics = {d.metric for d, _ in drafts}
    others = [
        Other(f.id, (f.metric, f.subsidiary, f.state, f.category, f.period_type, f.period),
              float(f.value_std), title)  # fmt: skip
        for f, title in db.execute(
            select(Fact, Document.title)
            .join(Document, Document.id == Fact.document_id)
            .where(Fact.metric.in_(metrics), Fact.document_id != doc.id,
                   Fact.status != FactStatus.REJECTED)  # fmt: skip
        ).all()
    ]
    facts = [d for d, _ in drafts]
    issues = validate(facts, others)
    flagged = {i.fact for i in issues}

    rows = []
    for index, (d, table_id) in enumerate(drafts):
        row = Fact(
            metric=d.metric,
            subsidiary=d.subsidiary,
            state=d.state,
            category=d.category,
            period_type=d.period_type,
            period=d.period,
            value_raw=d.value_raw,
            value=d.value,
            unit=d.unit,
            value_std=d.value_std,
            status=FactStatus.FLAGGED if index in flagged else FactStatus.VERIFIED,
            confidence=d.confidence,
            document_id=doc.id,
            page_no=d.page_no,
            bbox=d.bbox,
            table_id=table_id,
            label=d.label,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    for issue in issues:
        related = rows[issue.related_draft].id if issue.related_draft is not None else None
        db.add(
            ValidationIssue(
                fact_id=rows[issue.fact].id,
                rule_code=issue.rule,
                message=issue.message,
                severity=issue.severity,
                related_fact_id=related or issue.related_fact_id,
            )
        )
    db.commit()
    log.info("Document %s: %d facts, %d flagged", doc.id, len(rows), len(flagged))
    return len(issues)
