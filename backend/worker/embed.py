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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import LlmUnavailable, embed_texts
from app.models import Chunk
from worker.parse import BBox, Block, PageResult, Table

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


def _inside(block: Block, box: BBox) -> bool:
    """True if the block's centre lies inside `box`."""
    if block.bbox is None:
        return False
    cx, cy = (block.bbox[0] + block.bbox[2]) / 2, (block.bbox[1] + block.bbox[3]) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(c.replace("\n", " ").replace("|", "/") for c in cells) + " |"


def table_chunks(table: Table, page_no: int, max_words: int = MAX_WORDS) -> list[ChunkDraft]:
    """A table as a grid of rows, so the model can see which number is in which row and
    column. Long tables are split into row groups; each piece repeats the header row."""
    rows = [r for r in table.rows if any(c.strip() for c in r)]
    if not rows:
        return []
    title = f"Table on page {page_no}" + (f": {table.title}" if table.title else "")
    header, body = _row(rows[0]), [_row(r) for r in rows[1:]]
    budget = max(max_words - len(title.split()) - len(header.split()), 20)
    chunks, piece, words = [], [], 0
    for line in body or [""]:
        n = len(line.split())
        if piece and words + n > budget:
            chunks.append(ChunkDraft("\n".join([title, header, *piece]), table.bbox))
            piece, words = [], 0
        if line:
            piece.append(line)
            words += n
    chunks.append(ChunkDraft("\n".join([title, header, *piece]), table.bbox))
    return chunks


def page_chunks(page: PageResult, max_words: int = MAX_WORDS) -> list[ChunkDraft]:
    """Text chunks + table chunks for one page. Text blocks that sit inside a detected table
    are dropped: PyMuPDF also returns table cells as loose text, one value per line, which
    loses the row/column structure the table chunk keeps."""
    boxes = [t.bbox for t in page.tables if t.bbox]
    text_blocks = [b for b in page.blocks if not any(_inside(b, box) for box in boxes)]
    chunks = chunk_blocks(text_blocks, max_words)
    for table in page.tables:
        chunks.extend(table_chunks(table, page.page_no, max_words))
    return chunks


def embed_chunks(db: Session, chunks: list[Chunk]) -> bool:
    """Embed the given chunks in batches. Returns False if the model server is unavailable."""
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        try:
            vectors = embed_texts([c.text for c in batch])
        except LlmUnavailable as e:
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
