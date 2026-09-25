"""System health for the admin System status screen (guide W8: queue status, failed jobs,
storage use, model status).

Every check returns ok / warn / error with a short `code` the frontend translates and an
English `message` with the detail. A check never raises: a dependency that is down is
reported as such, so the screen still loads when Redis, the model server or even the
database is not there. Network checks use short timeouts and only talk to the configured
local services.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from redis import Redis
from rq import Queue, Worker
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.deps import scope_to_user
from app.llm import client
from app.models import Document, User
from app.models.enums import DocumentStatus

log = logging.getLogger(__name__)

Status = Literal["ok", "warn", "error"]
_RANK: dict[str, int] = {"ok": 0, "warn": 1, "error": 2}

BACKEND = Path(__file__).resolve().parents[2]
QUEUES = ("ingest", "topics", "reports")  # the queues the worker listens on (docker-compose)
TIMEOUT = 2.0  # seconds, for Redis and the model server
LOW_SPACE_BYTES = 5 * 1024**3  # warn below 5 GB free (or 10 %)
LOW_SPACE_SHARE = 0.10
NO_SPACE_BYTES = 1 * 1024**3  # error below 1 GB: uploads and page images will start failing


@dataclass
class Check:
    key: str
    status: Status
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueueInfo:
    name: str
    queued: int
    failed: int


@dataclass
class ModelInfo:
    name: str
    role: Literal["llm", "embed"]
    pulled: bool | None  # None: the server could not be asked


@dataclass
class StorageInfo:
    path: str
    free_bytes: int
    total_bytes: int


@dataclass
class SystemStatus:
    checks: list[Check] = field(default_factory=list)
    queues: list[QueueInfo] | None = None
    workers: int | None = None
    models: list[ModelInfo] = field(default_factory=list)
    storage: StorageInfo | None = None
    documents: dict[str, int] | None = None

    @property
    def overall(self) -> Status:
        return max((c.status for c in self.checks), key=_RANK.__getitem__, default="ok")


def _guard(key: str, fn: Callable[[], list[Check]]) -> list[Check]:
    """Run one group of checks; anything unexpected becomes an error for that group only."""
    try:
        return fn()
    except Exception as e:  # one broken check must not break the screen
        log.warning("Status check %s failed", key, exc_info=True)
        return [Check(key, "error", "check_failed", f"{e.__class__.__name__}: {e}")]


# --- database ------------------------------------------------------------------------------------


@lru_cache  # the migrations on disk do not change while the API runs
def migration_head() -> str | None:
    heads = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini"))).get_heads()
    return ", ".join(sorted(heads)) or None


def check_database(db: Session, user: User, status: SystemStatus) -> list[Check]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        _rollback(db)
        return [
            Check("database", "error", "unreachable", f"{e.__class__.__name__}: {e}"[:300]),
            Check("migrations", "error", "unknown", "The database could not be reached."),
        ]
    checks = [Check("database", "ok", "reachable", "The database answers.")]
    try:
        current = ", ".join(sorted(db.scalars(text("SELECT version_num FROM alembic_version"))))
    except Exception:  # no alembic_version table: never migrated
        _rollback(db)
        current = ""
    head = migration_head()
    details = {"current": current or None, "head": head}
    if not current:
        checks.append(
            Check("migrations", "error", "not_migrated", "Run `alembic upgrade head`.", details)
        )
    elif current != head:
        checks.append(
            Check(
                "migrations",
                "warn",
                "behind",
                f"Database is at {current}, the code expects {head}. Run `alembic upgrade head`.",
                details,
            )
        )
    else:
        checks.append(Check("migrations", "ok", "up_to_date", f"At {current}.", details))

    stmt = scope_to_user(
        select(Document.status, func.count()).group_by(Document.status), Document, user
    )
    counts = {s.value: 0 for s in DocumentStatus}
    for doc_status, n in db.execute(stmt).all():
        counts[getattr(doc_status, "value", doc_status)] = int(n)
    status.documents = counts
    failed = counts[DocumentStatus.FAILED.value]
    checks.append(
        Check(
            "documents",
            "warn" if failed else "ok",
            "failed_documents" if failed else "no_failures",
            f"{failed} document(s) failed to process." if failed else "No failed documents.",
            {"failed": failed},
        )
    )
    return checks


def _rollback(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


# --- Redis and the worker ------------------------------------------------------------------------


def redis_connection(url: str) -> Redis:
    return Redis.from_url(url, socket_connect_timeout=TIMEOUT, socket_timeout=TIMEOUT)


def check_redis(settings: Settings, status: SystemStatus) -> list[Check]:
    if settings.ingest_inline:
        return [
            Check(
                "redis",
                "ok",
                "not_used",
                "INGEST_INLINE=true: jobs run inside the API, Redis is not used.",
            )
        ]
    try:
        conn = redis_connection(settings.redis_url)
        conn.ping()
        queues = [Queue(name, connection=conn) for name in QUEUES]
        status.queues = [QueueInfo(q.name, q.count, q.failed_job_registry.count) for q in queues]
        status.workers = Worker.count(connection=conn)
    except Exception as e:  # redis.RedisError, or a bad REDIS_URL
        return [
            Check(
                "redis",
                "error",
                "unreachable",
                f"No answer from Redis ({e.__class__.__name__}); uploads cannot be processed.",
            ),
            Check("worker", "error", "unknown", "Redis could not be reached."),
        ]
    failed = sum(q.failed for q in status.queues)
    checks = [
        Check(
            "redis",
            "warn" if failed else "ok",
            "failed_jobs" if failed else "reachable",
            f"{failed} failed job(s) in the queues." if failed else "Redis answers.",
            {"failed": failed},
        )
    ]
    if status.workers:
        checks.append(Check("worker", "ok", "running", f"{status.workers} worker(s) running."))
    else:
        checks.append(
            Check(
                "worker",
                "error",
                "no_workers",
                "No worker is running: queued documents will not be processed.",
            )
        )
    return checks


# --- the model server ----------------------------------------------------------------------------


def fetch_tags(base: str) -> httpx.Response:
    return httpx.get(f"{base}/api/tags", timeout=TIMEOUT)


def check_model_server(settings: Settings, status: SystemStatus) -> list[Check]:
    wanted = [(settings.llm_model, "llm"), (settings.embed_model, "embed")]
    status.models = [ModelInfo(name, role, None) for name, role in wanted]
    try:
        base = client.base_url()
    except client.ExternalCallBlocked as e:
        return [Check("model_server", "error", "blocked", str(e))]
    try:
        res = fetch_tags(base)
    except httpx.HTTPError as e:
        # Optional: the app keeps working, but questions and drafts need the model.
        return [
            Check(
                "model_server",
                "warn",
                "unreachable",
                f"No answer from {base} ({e.__class__.__name__}). Questions and report drafts "
                "need it.",
            )
        ]
    if res.status_code == 404:  # a server without Ollama's model list (e.g. vLLM)
        return [Check("model_server", "ok", "no_model_list", f"{base} answers.")]
    if res.status_code != 200:
        return [Check("model_server", "warn", "server_error", f"{base}: HTTP {res.status_code}")]
    try:
        tags = res.json()
    except ValueError:
        return [Check("model_server", "warn", "server_error", f"{base}: reply is not JSON")]
    missing = client.missing_models([name for name, _ in wanted], tags)
    status.models = [ModelInfo(name, role, name not in missing) for name, role in wanted]
    checks = [Check("model_server", "ok", "reachable", f"{base} answers.")]
    if missing:
        checks.append(
            Check(
                "models",
                "warn",
                "models_missing",
                "Not pulled: " + ", ".join(missing) + ". Run `ollama pull <model>`.",
                {"missing": missing},
            )
        )
    else:
        checks.append(Check("models", "ok", "pulled", " and ".join(n for n, _ in wanted)))
    return checks


# --- storage -------------------------------------------------------------------------------------


def disk_usage(path: Path) -> tuple[int, int]:
    """(free, total) bytes of the disk holding `path`, or its nearest existing parent."""
    while not path.exists() and path.parent != path:
        path = path.parent
    usage = shutil.disk_usage(path)
    return usage.free, usage.total


def check_storage(settings: Settings, status: SystemStatus) -> list[Check]:
    path = Path(settings.storage_dir).resolve()
    free, total = disk_usage(path)
    status.storage = StorageInfo(str(path), free, total)
    gb = f"{free / 1024**3:.1f} GB free"
    if free < NO_SPACE_BYTES:
        return [Check("storage", "error", "no_space", f"{gb}: uploads will fail.")]
    if free < LOW_SPACE_BYTES or (total and free / total < LOW_SPACE_SHARE):
        return [Check("storage", "warn", "low_space", f"{gb}.")]
    return [Check("storage", "ok", "enough_space", f"{gb}.")]


# --- settings ------------------------------------------------------------------------------------


def check_external_calls(settings: Settings) -> list[Check]:
    if settings.allow_external_calls:
        return [
            Check(
                "external_calls",
                "warn",
                "allowed",
                "ALLOW_EXTERNAL_CALLS=true: text may be sent to a model server outside this "
                "network.",
            )
        ]
    return [Check("external_calls", "ok", "blocked", "Only the local model server is used.")]


def collect(db: Session, user: User, settings: Settings) -> SystemStatus:
    status = SystemStatus()
    status.checks = [
        *_guard("database", lambda: check_database(db, user, status)),
        *_guard("redis", lambda: check_redis(settings, status)),
        *_guard("model_server", lambda: check_model_server(settings, status)),
        *_guard("storage", lambda: check_storage(settings, status)),
        *_guard("external_calls", lambda: check_external_calls(settings)),
    ]
    return status
