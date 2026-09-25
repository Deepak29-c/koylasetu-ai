"""Metrics screen (guide 12 and 15.2): accuracy, time saved and automation from the latest
benchmark run, next to live usage numbers from this database.

The benchmark numbers come from eval/run_eval.py, which writes eval/results/<date>/summary.json
(ids, counts and percentages only). Live numbers are counted here, scoped to the caller's units
like every other query.
"""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import require, scope_to_user
from app.core.rbac import Permission
from app.models import Document, Fact, QaLog, Report, ReviewActionLog, User
from app.models.enums import FactStatus, ReportStatus
from app.schemas.metrics import (
    BenchmarkOut,
    FactMetricsOut,
    MetricsOut,
    QaMetricsOut,
    ReportMetricsOut,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _count(db: Session, stmt: Select) -> int:
    return db.scalar(stmt) or 0


def _pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


# Months are counted in Indian time: a question asked at 01:00 IST on the 1st is this month's.
IST = ZoneInfo("Asia/Kolkata")
# The repo root, so a relative EVAL_RESULTS_DIR works wherever the API was started from.
REPO_ROOT = Path(__file__).resolve().parents[3]


def _month_start() -> datetime:
    start = datetime.now(IST).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


def results_dir(setting: str) -> Path:
    path = Path(setting)
    return path if path.is_absolute() else (REPO_ROOT / "backend" / path).resolve()


_RUN_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d+))?$")


def _run_order(path: Path) -> tuple[str, int]:
    """run_eval.py names a day's runs 2026-09-26, 2026-09-26-2, 2026-09-26-3…"""
    m = _RUN_NAME.match(path.name)
    return (m.group(1), int(m.group(2) or 1)) if m else (path.name, 0)


def _qa(db: Session, user: User) -> QaMetricsOut:
    # A question belongs to the unit of the person who asked it.
    def scoped(*cols) -> Select:
        stmt = select(*cols).select_from(QaLog).join(User, User.id == QaLog.user_id)
        return scope_to_user(stmt, User, user)

    total = _count(db, scoped(func.count()))
    grounded = _count(db, scoped(func.count()).where(QaLog.grounded.is_(True)))
    score = QaLog.feedback["score"].as_integer()
    helpful = _count(db, scoped(func.count()).where(score == 1))
    not_helpful = _count(db, scoped(func.count()).where(score == -1))
    avg_latency = db.scalar(scoped(func.avg(QaLog.latency_ms)))
    return QaMetricsOut(
        questions_total=total,
        questions_this_month=_count(
            db, scoped(func.count()).where(QaLog.created_at >= _month_start())
        ),
        grounded=grounded,
        grounded_pct=_pct(grounded, total),
        avg_latency_ms=round(avg_latency) if avg_latency is not None else None,
        helpful=helpful,
        not_helpful=not_helpful,
        helpful_pct=_pct(helpful, helpful + not_helpful),
    )


def _facts(db: Session, user: User) -> FactMetricsOut:
    # Facts inherit their org unit from the document they came from.
    def scoped() -> Select:
        stmt = (
            select(func.count()).select_from(Fact).join(Document, Fact.document_id == Document.id)
        )
        return scope_to_user(stmt, Document, user)

    reviewed = exists().where(ReviewActionLog.fact_id == Fact.id)
    total = _count(db, scoped())
    auto = _count(db, scoped().where(Fact.status == FactStatus.VERIFIED, ~reviewed))
    return FactMetricsOut(
        total=total,
        auto_verified=auto,
        reviewed_verified=_count(db, scoped().where(Fact.status == FactStatus.VERIFIED, reviewed)),
        flagged=_count(db, scoped().where(Fact.status == FactStatus.FLAGGED)),
        rejected=_count(db, scoped().where(Fact.status == FactStatus.REJECTED)),
        automation_pct=_pct(auto, total),
    )


def _reports(db: Session, user: User) -> ReportMetricsOut:
    def scoped() -> Select:
        return scope_to_user(select(func.count()).select_from(Report), Report, user)

    return ReportMetricsOut(
        total=_count(db, scoped()),
        drafts=_count(
            db, scoped().where(Report.status.in_((ReportStatus.DRAFT, ReportStatus.RETURNED)))
        ),
        in_review=_count(db, scoped().where(Report.status == ReportStatus.IN_REVIEW)),
        approved=_count(
            db,
            scoped().where(Report.status.in_((ReportStatus.APPROVED, ReportStatus.EXPORTED))),
        ),
    )


def _num(value) -> float | None:
    return value if isinstance(value, int | float) and not isinstance(value, bool) else None


def latest_benchmark(results_dir: Path) -> BenchmarkOut | None:
    """The newest run's summary.json, or None when the benchmark has not been run here."""
    try:
        runs = sorted(
            (p for p in results_dir.iterdir() if (p / "summary.json").is_file()),
            key=_run_order,
        )
    except OSError:
        return None
    if not runs:
        return None
    try:
        s = json.loads((runs[-1] / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.warning("Could not read benchmark summary in %s: %s", runs[-1], e)
        return None

    def extra(key: str) -> float | None:
        section = s.get(key)
        return _num(section.get("pct")) if isinstance(section, dict) else None

    latency = s.get("latency_ms") if isinstance(s.get("latency_ms"), dict) else {}
    p50 = _num(latency.get("p50"))
    return BenchmarkOut(
        run_date=str(s.get("run_date") or runs[-1].name),
        questions_asked=int(_num(s.get("questions_asked")) or 0),
        answered=int(_num(s.get("answered")) or 0),
        not_found=int(_num(s.get("not_found")) or 0),
        errors=int(_num(s.get("errors")) or 0),
        numeric_accuracy_pct=_num(s.get("numeric_accuracy_pct")),
        all_correct_pct=_num(s.get("all_correct_pct")),
        grounded_pct=_num(s.get("grounded_pct")),
        median_latency_ms=round(p50) if p50 is not None else None,
        time_saved_pct=extra("time_saved"),
        citation_correct_pct=extra("citations"),
        automation_pct=extra("automation"),
    )


@router.get("", response_model=MetricsOut)
def metrics(
    user: User = Depends(require(Permission.VIEW_METRICS)),
    db: Session = Depends(get_db),
) -> MetricsOut:
    return MetricsOut(
        qa=_qa(db, user),
        facts=_facts(db, user),
        reports=_reports(db, user),
        benchmark=latest_benchmark(results_dir(get_settings().eval_results_dir)),
    )
