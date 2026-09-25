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
