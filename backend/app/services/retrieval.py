"""Hybrid retrieval (guide 9.1): full-text + vector search, merged with reciprocal rank fusion.

Every query goes through scope_to_user, so a user only ever gets passages from documents
their org unit may see. Vector search is skipped when embeddings are not available.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import scope_to_user
from app.llm.client import LlmUnavailable, embed_texts
from app.models import Chunk, Document, User
from app.services.normalise import to_ascii_digits

log = logging.getLogger(__name__)

CANDIDATES = 30  # per search method (guide 9.1)
TOP_K = 6  # passages given to the model (guide: 6-8)
RRF_K = 60

# Words that carry no meaning for search. Includes the formal phrasing of PQs.
STOPWORDS = set(
    """a an the and or of in on at to for from by with as is are was were be been being this that
    these those it its if so than then there their them they we our you your he she his her what
    which who whom whose when where why how whether any all each other such into over under about
    during up down out also not no nor only same too very can will shall may might must would
    should could do does did has have had details thereof state please government minister
    pleased country india indian number steps taken reason reasons regard year years""".split()
)
HINDI_STOPWORDS = {
    "का",
    "की",
    "के",
    "है",
    "हैं",
    "में",
    "से",
    "को",
    "और",
    "या",
    "क्या",
    "यदि",
    "तो",
}
_TOKEN = re.compile(r"[0-9A-Za-zऀ-ॿ]+")


@dataclass
class Passage:
    ref: str  # "C1", "C2"… the id the model cites
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_no: int
    bbox: list[float] | None
    text: str


def search_terms(question: str) -> list[str]:
    seen: list[str] = []
    for tok in _TOKEN.findall(to_ascii_digits(question).lower()):
        if tok in STOPWORDS or tok in HINDI_STOPWORDS or (len(tok) < 2 and not tok.isdigit()):
            continue
        if tok not in seen:
            seen.append(tok)
    return seen


def to_tsquery_text(terms: list[str]) -> str:
    """OR the terms (ranking rewards chunks that match more of them); prefix-match longer words
    so 'production' also finds 'productions'. Tokens are [0-9A-Za-z + Devanagari] only, so the
    string is safe to pass to to_tsquery."""
    return " | ".join(f"{t}:*" if len(t) >= 4 and not t.isdigit() else t for t in terms)


def rrf(rankings: list[list[uuid.UUID]], k: int = RRF_K) -> list[uuid.UUID]:
    scores: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda c: scores[c], reverse=True)


def keyword_ids(db: Session, user: User, question: str) -> list[uuid.UUID]:
    terms = search_terms(question)
    if not terms:
        return []
    query = func.to_tsquery("simple", to_tsquery_text(terms))
    rank = func.ts_rank_cd(Chunk.tsv, query)
    stmt = (
        select(Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.tsv.op("@@")(query))
        .order_by(rank.desc())
        .limit(CANDIDATES)
    )
    return list(db.scalars(scope_to_user(stmt, Document, user)))


def vector_ids(db: Session, user: User, question: str) -> list[uuid.UUID]:
    try:
        (vector,) = embed_texts([question], timeout=60)
    except LlmUnavailable as e:
        log.info("Vector search skipped: %s", e)
        return []
    stmt = (
        select(Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.embedding.is_not(None))
        .order_by(Chunk.embedding.cosine_distance(vector))
        .limit(CANDIDATES)
    )
    return list(db.scalars(scope_to_user(stmt, Document, user)))


def hybrid_search(db: Session, user: User, question: str, top_k: int = TOP_K) -> list[Passage]:
    ranked = rrf([keyword_ids(db, user, question), vector_ids(db, user, question)])[:top_k]
    if not ranked:
        return []
    rows = db.execute(
        select(Chunk, Document.title)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(ranked))
    ).all()
    by_id = {chunk.id: (chunk, title) for chunk, title in rows}
    passages = []
    for chunk_id in ranked:
        chunk, title = by_id[chunk_id]
        passages.append(
            Passage(
                ref=f"C{len(passages) + 1}",
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_title=title,
                page_no=chunk.page_no,
                bbox=chunk.bbox,
                text=chunk.text,
            )
        )
    return passages
