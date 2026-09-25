"""INGEST_INLINE: without Redis (e.g. Windows without Docker) the API runs the same worker
functions itself, one job at a time, instead of leaving uploads stuck at UPLOADED."""

import threading
import uuid

import pytest

from app.core.config import get_settings
from app.services import queue


@pytest.fixture
def inline(monkeypatch):
    monkeypatch.setenv("INGEST_INLINE", "true")
    get_settings.cache_clear()
    queue._inline = None
    yield
    if queue._inline is not None:
        queue._inline.shutdown(wait=True)
        queue._inline = None
    get_settings.cache_clear()


def _no_redis(*_a, **_k):
    raise AssertionError("inline mode must not touch Redis")


def test_inline_ingest_runs_the_worker_job_in_order(inline, monkeypatch):
    import worker.ingest
    import worker.topics

    ran, threads = [], set()

    def fake_process(doc_id):
        ran.append(("ingest", doc_id))
        threads.add(threading.current_thread().name)

    monkeypatch.setattr(worker.ingest, "process_document", fake_process)
    monkeypatch.setattr(
        worker.topics, "refresh_topics", lambda force: ran.append(("topics", force))
    )
    monkeypatch.setattr(queue.Redis, "from_url", _no_redis)

    a, b = uuid.uuid4(), uuid.uuid4()
    assert queue.enqueue_ingest(a) is True
    assert queue.enqueue_ingest(b) is True
    assert queue.enqueue_topics_refresh(force=True) is True
    queue._inline.shutdown(wait=True)

    assert ran == [("ingest", str(a)), ("ingest", str(b)), ("topics", True)]
    assert len(threads) == 1 and threading.current_thread().name not in threads


def test_a_failing_inline_job_does_not_stop_the_next(inline, monkeypatch):
    import worker.ingest

    ran = []

    def flaky(doc_id):
        ran.append(doc_id)
        if len(ran) == 1:
            raise RuntimeError("scanned page, no OCR")

    monkeypatch.setattr(worker.ingest, "process_document", flaky)
    first, second = uuid.uuid4(), uuid.uuid4()
    queue.enqueue_ingest(first)
    queue.enqueue_ingest(second)
    queue._inline.shutdown(wait=True)
    assert ran == [str(first), str(second)]


def test_default_still_uses_redis_and_reports_when_it_is_down(monkeypatch):
    from redis.exceptions import ConnectionError as RedisConnectionError

    monkeypatch.delenv("INGEST_INLINE", raising=False)
    get_settings.cache_clear()

    def down(*_a, **_k):
        raise RedisConnectionError("refused")

    monkeypatch.setattr(queue.Redis, "from_url", down)
    try:
        assert queue.enqueue_ingest(uuid.uuid4()) is False
        assert queue.enqueue_topics_refresh() is False
        assert queue._inline is None  # nothing ran in the API process
    finally:
        get_settings.cache_clear()
