"""Similar past Parliament questions (guide sections 10.2 and 13: GET /pq/similar).

Two kinds of candidates:
  approved_reply  PQ replies that were approved (or approved and exported) in this system,
                  matched on their question: subject line + question text.
  pq_document     uploaded Parliament question answers (doc_type pq_answer), matched on the
                  text of their chunks, one result per document.

Each kind is ranked by full-text search ('simple' config, so Hindi and English work the same)
and, when the local model server answers, by embedding distance too. The rankings are merged
with reciprocal rank fusion, as in retrieval.hybrid_search, so the panel still works when the
model server is not running. Every query goes through scope_to_user.
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Text, cast, func, literal_column, select
from sqlalchemy.orm import Session

from app.core.deps import scope_to_user
from app.llm.client import LlmUnavailable, embed_texts
from app.models import Chunk, Document, ParliamentQuestion, Report, User
from app.models.enums import DocType, ReportStatus, ReportType
from app.services.normalise import to_ascii_digits
from app.services.retrieval import RRF_K, search_terms, to_tsquery_text

log = logging.getLogger(__name__)

MIN_TEXT = 3  # shorter input gives an empty list
MAX_TEXT = 4000  # what is searched and embedded; a PQ is rarely longer
MAX_TERMS = 40
CANDIDATES = 30  # per kind and search method
SNIPPET = 240
EMBED_TIMEOUT = 30
# Cosine distance beyond which a vector match is not a similar question (0 = same meaning).
MAX_DISTANCE = 0.45
DONE_STATUSES = (ReportStatus.APPROVED, ReportStatus.EXPORTED)
_TOKEN = re.compile(r"[0-9A-Za-zऀ-ॿ]+")  # the words search_terms reads

# Keys in the fused ranking: ("report", report id) or ("chunk", chunk id).
Key = tuple[str, uuid.UUID]


@dataclass
class Similar:
    kind: str  # "approved_reply" | "pq_document"
    title: str
    house: str | None
    q_type: str | None
    q_no: str | None
    answer_date: date | None
    snippet: str
    answer: str | None
    score: float
    report_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    document_title: str | None = None
    page: int | None = None
    chunk_id: uuid.UUID | None = None


# --- pure helpers ------------------------------------------------------------------------------


def clean(text: str | None) -> str:
    return " ".join((text or "").split())


def report_question(content: dict | None) -> str:
    """The question a PQ reply answers, read from its content_json: the header's subject line
    and each block's question. Replies saved as plain text only have `text`."""
    content = content or {}
    header = content.get("header") or {}
    parts = [header.get("subject") or ""]
    parts += [b.get("question") or "" for b in content.get("blocks") or [] if isinstance(b, dict)]
    question = clean(" ".join(parts))
    return question or clean(content.get("text"))


def report_answer(content: dict | None) -> str:
    """The reply's answer text, part by part, for a short preview."""
    blocks = (content or {}).get("blocks") or []
    return clean(
        " ".join(
            b.get("text") or "" for b in blocks if isinstance(b, dict) and not b.get("not_found")
        )
    )


def excerpt(text: str | None, terms: list[str], width: int = SNIPPET) -> str:
    """About `width` characters of `text`, starting a little before the first search term found
    in it, cut on word boundaries and marked with an ellipsis where text was left out."""
    text = clean(text)
    if len(text) <= width:
        return text
    lower = text.lower()
    hits = [i for i in (lower.find(t) for t in terms if t) if i >= 0]
    start = max(0, min(hits) - width // 4) if hits else 0
    if start:
        space = text.find(" ", start)
        start = space + 1 if 0 <= space < start + 20 else start
    end = min(len(text), start + width)
    if end < len(text):
        space = text.rfind(" ", start, end)
        end = space if space > start + width // 2 else end
    return f"{'… ' if start else ''}{text[start:end].strip()}{' …' if end < len(text) else ''}"


def words_needed(terms: list[str]) -> int:
    """How many search words a keyword match must share with the input to count as similar.
    Search ORs the words, and nearly every question here mentions coal, so one shared word
    is not enough once there are several."""
    n = len(terms)
    return n if n < 2 else max(2, math.ceil(n / 4))


def shared_words(terms: list[str], text: str | None) -> int:
    """How many of `terms` occur in `text`, matched the way the search matches them: longer
    words as prefixes ('production' finds 'productions'), short words and numbers exactly."""
    words = set(_TOKEN.findall(to_ascii_digits(text or "").lower()))
    count = 0
    for t in terms:
        prefix = len(t) >= 4 and not t.isdigit()
        if t in words or (prefix and any(w.startswith(t) for w in words)):
            count += 1
    return count


def reply_search_text(report: Report, pq: ParliamentQuestion | None) -> str:
    """The same text the reply keyword search looks at."""
    content = report.content_json or {}
    return " ".join(
        [report.title or "", (pq.subject or "") if pq else "", pq.question_text if pq else ""]
        + [report_question(content)]
    )


def fuse(rankings: list[list[Key]], k: int = RRF_K) -> list[tuple[Key, float]]:
    """Reciprocal rank fusion over several rankings, best first, with the fused score."""
    scores: dict[Key, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def query_vector(text: str) -> list[float] | None:
    try:
        (vector,) = embed_texts([text], timeout=EMBED_TIMEOUT)
    except LlmUnavailable as e:
        log.info("Similar PQs: vector search skipped: %s", e)
        return None
    return vector


# --- queries -----------------------------------------------------------------------------------


def _reply_text():
    """Searchable text of an approved reply: its title, the stored question and the question
    parts in content_json (for replies whose question row is missing)."""
    blocks = func.jsonb_path_query_array(
        Report.content_json, literal_column("'$.blocks[*].question'::jsonpath")
    )
    return func.concat_ws(
        " ",
        Report.title,
        ParliamentQuestion.subject,
        ParliamentQuestion.question_text,
        Report.content_json[("header", "subject")].astext,
        cast(blocks, Text),
    )


def _replies(user: User, exclude: uuid.UUID | None):
    stmt = (
        select(Report.id)
        .outerjoin(ParliamentQuestion, ParliamentQuestion.id == Report.pq_id)
        .where(Report.report_type == ReportType.PQ_REPLY, Report.status.in_(DONE_STATUSES))
    )
    if exclude is not None:
        stmt = stmt.where(Report.id != exclude)
    return scope_to_user(stmt, Report, user)


def reply_keyword_stmt(user: User, terms: list[str], exclude: uuid.UUID | None = None):
    query = func.to_tsquery("simple", to_tsquery_text(terms))
    tsv = func.to_tsvector("simple", _reply_text())
    return (
        _replies(user, exclude)
        .where(tsv.op("@@")(query))
        .order_by(func.ts_rank_cd(tsv, query).desc())
        .limit(CANDIDATES)
    )


def reply_vector_stmt(user: User, vector: list[float], exclude: uuid.UUID | None = None):
    return (
        _replies(user, exclude)
        .where(ParliamentQuestion.embedding.is_not(None))
        .where(ParliamentQuestion.embedding.cosine_distance(vector) < MAX_DISTANCE)
        .order_by(ParliamentQuestion.embedding.cosine_distance(vector))
        .limit(CANDIDATES)
    )


def _pq_chunks(user: User):
    stmt = (
        select(Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.doc_type == DocType.PQ_ANSWER)
    )
    return scope_to_user(stmt, Document, user)


def chunk_keyword_stmt(user: User, terms: list[str]):
    query = func.to_tsquery("simple", to_tsquery_text(terms))
    return (
        _pq_chunks(user)
        .where(Chunk.tsv.op("@@")(query))
        .order_by(func.ts_rank_cd(Chunk.tsv, query).desc())
        .limit(CANDIDATES)
    )


def chunk_vector_stmt(user: User, vector: list[float]):
    return (
        _pq_chunks(user)
        .where(Chunk.embedding.is_not(None))
        .where(Chunk.embedding.cosine_distance(vector) < MAX_DISTANCE)
        .order_by(Chunk.embedding.cosine_distance(vector))
        .limit(CANDIDATES)
    )


def rankings(
    db: Session,
    user: User,
    text: str,
    *,
    include_replies: bool,
    exclude: uuid.UUID | None = None,
) -> tuple[list[list[Key]], set[Key], list[str]]:
    """The keyword and vector rankings of both kinds (approved replies first, so they win a
    tie), the keys found by meaning, and the search terms used."""
    terms = search_terms(text)[:MAX_TERMS]
    vector = query_vector(text)
    lists: list[list[Key]] = []
    by_meaning: set[Key] = set()

    def run(kind: str, stmt) -> list[Key]:
        keys = [(kind, i) for i in db.scalars(stmt)]
        lists.append(keys)
        return keys

    if terms:
        if include_replies:
            run("report", reply_keyword_stmt(user, terms, exclude))
        run("chunk", chunk_keyword_stmt(user, terms))
    if vector is not None:
        if include_replies:
            by_meaning.update(run("report", reply_vector_stmt(user, vector, exclude)))
        by_meaning.update(run("chunk", chunk_vector_stmt(user, vector)))
    return lists, by_meaning, terms


def _load_reports(db: Session, user: User, ids: list[uuid.UUID]) -> dict:
    if not ids:
        return {}
    stmt = (
        select(Report, ParliamentQuestion)
        .outerjoin(ParliamentQuestion, ParliamentQuestion.id == Report.pq_id)
        .where(Report.id.in_(ids))
    )
    return {r.id: (r, pq) for r, pq in db.execute(scope_to_user(stmt, Report, user)).all()}


def _load_chunks(db: Session, user: User, ids: list[uuid.UUID]) -> dict:
    if not ids:
        return {}
    stmt = (
        select(Chunk, Document, ParliamentQuestion)
        .join(Document, Document.id == Chunk.document_id)
        .outerjoin(ParliamentQuestion, ParliamentQuestion.document_id == Document.id)
        .where(Chunk.id.in_(ids))
    )
    found: dict = {}
    for chunk, doc, pq in db.execute(scope_to_user(stmt, Document, user)).all():
        found.setdefault(chunk.id, (chunk, doc, pq))
    return found


def _enum(value) -> str | None:
    return None if value is None else getattr(value, "value", value)


def reply_item(report: Report, pq: ParliamentQuestion | None, terms: list[str], score: float):
    content = report.content_json or {}
    header = content.get("header") or {}
    question = clean(pq.question_text) if pq else report_question(content)
    answer = report_answer(content)
    return Similar(
        kind="approved_reply",
        title=clean(pq.subject if pq and pq.subject else header.get("subject")) or report.title,
        house=_enum(pq.house) if pq else header.get("house") or None,
        q_type=_enum(pq.q_type) if pq else header.get("q_type") or None,
        q_no=(pq.q_no if pq else header.get("q_no")) or None,
        answer_date=pq.answer_date if pq else report.due_date,
        snippet=excerpt(question, terms),
        answer=excerpt(answer, terms) or None,
        score=round(score, 5),
        report_id=report.id,
    )


def document_item(
    chunk: Chunk, doc: Document, pq: ParliamentQuestion | None, terms: list[str], score: float
):
    return Similar(
        kind="pq_document",
        title=clean(pq.subject) if pq and pq.subject else doc.title,
        house=_enum(pq.house) if pq else None,
        q_type=_enum(pq.q_type) if pq else None,
        q_no=pq.q_no if pq else None,
        answer_date=pq.answer_date if pq else None,
        snippet=excerpt(chunk.text, terms),
        answer=(excerpt(pq.answer_text, terms) or None) if pq else None,
        score=round(score, 5),
        document_id=doc.id,
        document_title=doc.title,
        page=chunk.page_no,
        chunk_id=chunk.id,
    )


def find_similar(
    db: Session,
    user: User,
    text: str,
    *,
    limit: int = 5,
    include_replies: bool = True,
    exclude: uuid.UUID | None = None,
) -> list[Similar]:
    text = clean(text)[:MAX_TEXT]
    if len(text) < MIN_TEXT:
        return []
    lists, by_meaning, terms = rankings(
        db, user, text, include_replies=include_replies, exclude=exclude
    )
    fused = fuse(lists)
    if not fused:
        return []
    reports = _load_reports(db, user, [i for kind, i in (k for k, _ in fused) if kind == "report"])
    chunks = _load_chunks(db, user, [i for kind, i in (k for k, _ in fused) if kind == "chunk"])
    needed = words_needed(terms)

    items: list[Similar] = []
    seen_docs: set[uuid.UUID] = set()
    for (kind, key), score in fused:
        close = (kind, key) in by_meaning
        if kind == "report" and key in reports:
            report, pq = reports[key]
            if close or shared_words(terms, reply_search_text(report, pq)) >= needed:
                items.append(reply_item(report, pq, terms, score))
        elif kind == "chunk" and key in chunks:
            chunk, doc, pq = chunks[key]
            if doc.id in seen_docs:  # one result per document: its best-matching chunk
                continue
            if close or shared_words(terms, chunk.text) >= needed:
                seen_docs.add(doc.id)
                items.append(document_item(chunk, doc, pq, terms, score))
        if len(items) >= limit:
            break
    return items


def pq_text(pq: ParliamentQuestion) -> str:
    return clean(f"{pq.subject or ''} {pq.question_text}")[:MAX_TEXT]


def remember(db: Session, report: Report) -> None:
    """Embed an approved reply's question so vector search can find it later. Best effort:
    without the model server the reply is still found by keyword search."""
    if report.report_type != ReportType.PQ_REPLY or report.pq_id is None:
        return
    pq = db.get(ParliamentQuestion, report.pq_id)
    if pq is None or pq.embedding is not None:
        return
    try:
        (pq.embedding,) = embed_texts([pq_text(pq)], timeout=EMBED_TIMEOUT)
    except LlmUnavailable as e:
        log.info("Approved PQ %s not embedded: %s", pq.id, e)
