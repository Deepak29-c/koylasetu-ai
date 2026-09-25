"""Chunking and embeddings (guide 7.1 steps 8-9).

Chunks never cross a page, so every chunk can be cited as (document, page) and highlighted
with its bbox. Embeddings come from the local model server (Ollama, EMBED_MODEL=bge-m3).
If it is not running, chunks are saved without embeddings: keyword search still works, and
`embed_missing()` fills them in later.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Chunk
from app.models.document import EMBED_DIM
from worker.parse import BBox, Block

log = logging.getLogger(__name__)

# ~300-500 tokens (guide 7.1); for English prose 1 token is about 0.75 words.
MAX_WORDS = 350
EMBED_BATCH = 16


@dataclass
class ChunkDraft:
    text: str
    bbox: BBox | None


def _union(a: BBox | None, b: BBox | None) -> BBox | None:
    if a is None:
        return b
    if b is None:
        return a
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def chunk_blocks(blocks: list[Block], max_words: int = MAX_WORDS) -> list[ChunkDraft]:
    """Group consecutive blocks of one page into chunks of at most `max_words` words.

    Splits on block (paragraph) boundaries. A single block longer than the limit is cut
    into word windows that all keep that block's bbox.
    """
    chunks: list[ChunkDraft] = []
    texts: list[str] = []
    words = 0
    bbox: BBox | None = None

    def flush() -> None:
        nonlocal texts, words, bbox
        if texts:
            chunks.append(ChunkDraft("\n".join(texts), bbox))
        texts, words, bbox = [], 0, None

    for block in blocks:
        n = len(block.text.split())
        if n == 0:
            continue
        if n > max_words:
            flush()
            tokens = block.text.split()
            for start in range(0, n, max_words):
                chunks.append(ChunkDraft(" ".join(tokens[start : start + max_words]), block.bbox))
            continue
        if words + n > max_words:
            flush()
        texts.append(block.text)
        words += n
        bbox = _union(bbox, block.bbox)
    flush()
    return chunks


class EmbeddingUnavailable(Exception):
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    try:
        res = httpx.post(
            f"{s.llm_base_url.rstrip('/')}/api/embed",
            json={"model": s.embed_model, "input": texts},
            timeout=300,
        )
    except httpx.HTTPError as e:
        raise EmbeddingUnavailable(f"model server not reachable at {s.llm_base_url}: {e}") from e
    if res.status_code != 200:
        raise EmbeddingUnavailable(f"model server error {res.status_code}: {res.text[:200]}")
    vectors = res.json().get("embeddings", [])
    if len(vectors) != len(texts) or any(len(v) != EMBED_DIM for v in vectors):
        raise EmbeddingUnavailable(
            f"expected {len(texts)} vectors of size {EMBED_DIM} from {s.embed_model}"
        )
    return vectors


def embed_chunks(db: Session, chunks: list[Chunk]) -> bool:
    """Embed the given chunks in batches. Returns False if the model server is unavailable."""
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        try:
            vectors = embed_texts([c.text for c in batch])
        except EmbeddingUnavailable as e:
            log.warning("Embeddings skipped: %s", e)
            return False
        for chunk, vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
        db.commit()
    return True


def embed_document(db: Session, document_id: uuid.UUID) -> bool:
    chunks = list(
        db.scalars(
            select(Chunk)
            .where(Chunk.document_id == document_id, Chunk.embedding.is_(None))
            .order_by(Chunk.page_no)
        )
    )
    return embed_chunks(db, chunks)


def embed_missing() -> int:
    """Worker job: embed every chunk that has no embedding yet. Returns how many were done."""
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        chunks = list(db.scalars(select(Chunk).where(Chunk.embedding.is_(None))))
        before = len(chunks)
        embed_chunks(db, chunks)
        return before - sum(1 for c in chunks if c.embedding is None)
