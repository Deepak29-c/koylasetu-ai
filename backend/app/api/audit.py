from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require
from app.core.rbac import Permission
from app.models import AuditLog, User
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    action: str | None = Query(None),
    entity: str | None = Query(None),
    user_email: str | None = Query(None, description="Filter by (part of) the actor's email"),
    from_date: date | None = Query(None, description="Only entries on/after this date"),
    to_date: date | None = Query(None, description="Only entries on/before this date"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: User = Depends(require(Permission.VIEW_AUDIT)),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    """Who did what, when — for Admins and Approvers (guide 2.1)."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if user_email:
        stmt = stmt.where(AuditLog.user.has(User.email.ilike(f"%{user_email}%")))
    if from_date:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        stmt = stmt.where(AuditLog.created_at <= datetime.combine(to_date, time.max))
    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt))


@router.get("/actions", response_model=list[str])
def list_actions(
    _: User = Depends(require(Permission.VIEW_AUDIT)),
    db: Session = Depends(get_db),
) -> list[str]:
    """Distinct action names seen so far, to populate the filter dropdown."""
    rows = db.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action))
    return list(rows)
