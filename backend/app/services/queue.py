import logging
import uuid

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from app.core.config import get_settings

log = logging.getLogger(__name__)


def enqueue_ingest(document_id: uuid.UUID) -> bool:
    """Queue the ingestion job. Returns False if Redis is unreachable (doc stays UPLOADED,
    and the operator can press Retry later)."""
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
    try:
        conn = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
        Queue("topics", connection=conn).enqueue(
            "worker.topics.refresh_topics", force, job_timeout=1800
        )
        return True
    except RedisError:
        log.warning("Could not queue topics job: Redis unreachable")
        return False
