"""Background jobs: RQ on Redis normally; inside the API process when INGEST_INLINE=true.

The inline mode is for machines without Redis / RQ, e.g. Windows without Docker (RQ needs
`fork`). Jobs then run one at a time on a single background thread of the API, using exactly
the same functions the RQ worker runs, so uploads still get processed.
"""

import logging
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from app.core.config import get_settings

log = logging.getLogger(__name__)

# One thread: jobs run in order, so documents don't compete for the database or the model.
_inline: ThreadPoolExecutor | None = None


def _run_inline(fn: Callable, *args) -> Future:
    global _inline
    if _inline is None:
        _inline = ThreadPoolExecutor(max_workers=1, thread_name_prefix="inline-jobs")

    def job() -> None:
        try:
            fn(*args)
        except Exception:  # the job records its own failure (e.g. document FAILED); log the rest
            log.exception("Inline job %s%s failed", getattr(fn, "__name__", fn), args)

    return _inline.submit(job)


def enqueue_ingest(document_id: uuid.UUID) -> bool:
    """Queue the ingestion job. Returns False if Redis is unreachable (doc stays UPLOADED,
    and the operator can press Retry later)."""
    if get_settings().ingest_inline:
        from worker.ingest import process_document

        _run_inline(process_document, str(document_id))
        return True
    try:
        conn = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
        Queue("ingest", connection=conn).enqueue(
            "worker.ingest.process_document", str(document_id), job_timeout=3600
        )
        return True
    except RedisError:
        log.warning("Could not queue ingest job for %s: Redis unreachable", document_id)
        return False


def enqueue_topics_refresh(force: bool = False) -> bool:
    """Queue the topic job (guide 11): read new PQs from ingested PQ answers, then re-build
    the topics if enough new questions arrived (or always, with force). False if Redis is
    unreachable."""
    if get_settings().ingest_inline:
        from worker.topics import refresh_topics

        _run_inline(refresh_topics, force)
        return True
    try:
        conn = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
        Queue("topics", connection=conn).enqueue(
            "worker.topics.refresh_topics", force, job_timeout=1800
        )
        return True
    except RedisError:
        log.warning("Could not queue topics job: Redis unreachable")
        return False
