"""Administration screens (guide W8): validation rules, report templates, system status.

All read-only. Rules and templates are described from the code that applies them
(worker/validate.py RULES, services/report_templates.py), so the screens cannot drift from
what the system actually does.
"""

from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import require, scope_to_user
from app.core.rbac import Permission
from app.models import Document, Fact, User, ValidationIssue
from app.models.enums import IssueStatus
from app.schemas.admin import RuleOut, SystemStatusOut, TemplateOut
from app.services import report_templates, system_status
from worker.validate import RULES

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    user: User = Depends(require(Permission.MANAGE_ADMIN)),
    db: Session = Depends(get_db),
) -> list[RuleOut]:
    stmt = (
        select(ValidationIssue.rule_code, func.count())
        .join(Fact, Fact.id == ValidationIssue.fact_id)
        .join(Document, Document.id == Fact.document_id)
        .where(ValidationIssue.status == IssueStatus.OPEN)
        .group_by(ValidationIssue.rule_code)
    )
    open_issues = {code: int(n) for code, n in db.execute(scope_to_user(stmt, Document, user))}
    return [
        RuleOut(
            code=r.code,
            name=r.name,
            checks=r.checks,
            severities=[s.value for s in r.severities],
            thresholds=[asdict(t) for t in r.thresholds],
            uses_other_documents=r.uses_other_documents,
            open_issues=open_issues.get(r.code, 0),
        )
        for r in RULES
    ]


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(_: User = Depends(require(Permission.MANAGE_ADMIN))) -> list[dict]:
    return [{**asdict(t), "report_type": t.report_type.value} for t in report_templates.templates()]


@router.get("/status", response_model=SystemStatusOut)
def get_status(
    user: User = Depends(require(Permission.MANAGE_ADMIN)),
    db: Session = Depends(get_db),
) -> SystemStatusOut:
    settings = get_settings()
    status = system_status.collect(db, user, settings)
    return SystemStatusOut(
        checked_at=datetime.now(UTC),
        version=__version__,
        overall=status.overall,
        flags={
            "ingest_inline": settings.ingest_inline,
            "allow_external_calls": settings.allow_external_calls,
        },
        **asdict(status),
    )
