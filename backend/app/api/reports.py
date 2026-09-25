import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require, scope_to_user
from app.core.rbac import Permission, has_permission
from app.models import Report, ReportVersion, User
from app.models.enums import ReportChangeKind, ReportStatus, ReportType
from app.schemas.report import (
    RejectIn,
    ReportCreateIn,
    ReportOut,
    ReportUpdateIn,
    ReportVersionOut,
)
from app.services import audit, similar_pq

router = APIRouter(prefix="/reports", tags=["reports"])

# Who can move a report from which status to which (guide section 10 workflow).
_EDITABLE_STATUSES = {ReportStatus.DRAFT, ReportStatus.RETURNED}
# Any of these is enough to *view* reports; editing/approving/exporting stay separately gated.
_VIEW_PERMISSIONS = (Permission.EDIT_REPORTS, Permission.APPROVE_REPORTS, Permission.EXPORT_REPORTS)


def require_view_reports(user: User = Depends(get_current_user)) -> User:
    if not any(has_permission(user.roles, p) for p in _VIEW_PERMISSIONS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot do this")
    return user


def _get_scoped(db: Session, report_id: uuid.UUID, user: User) -> Report:
    report = db.scalar(scope_to_user(select(Report).where(Report.id == report_id), Report, user))
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


@router.get("", response_model=list[ReportOut])
def list_reports(
    status_filter: ReportStatus | None = Query(None, alias="status"),
    report_type: ReportType | None = Query(None),
    user: User = Depends(require_view_reports),
    db: Session = Depends(get_db),
) -> list[Report]:
    stmt = scope_to_user(select(Report), Report, user).order_by(Report.created_at.desc())
    if status_filter:
        stmt = stmt.where(Report.status == status_filter)
    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
    return list(db.scalars(stmt.limit(500)))


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    body: ReportCreateIn,
    request: Request,
    user: User = Depends(require(Permission.EDIT_REPORTS)),
    db: Session = Depends(get_db),
) -> Report:
    report = Report(
        report_type=body.report_type,
        title=body.title,
        status=ReportStatus.DRAFT,
        content_json=body.content_json,
        org_unit_id=user.org_unit_id,
        created_by=user.id,
        due_date=body.due_date,
    )
    db.add(report)
    db.flush()
    db.add(
        ReportVersion(
            report_id=report.id,
            version=1,
            content_json=body.content_json,
            edited_by=user.id,
            change_kind=ReportChangeKind.CREATED,
        )
    )
    audit.record(
        db,
        "create_report",
        actor=user,
        entity="report",
        entity_id=report.id,
        details={"report_type": report.report_type.value, "title": report.title},
        request=request,
    )
    db.commit()
    db.refresh(report)
    return report


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: uuid.UUID,
    user: User = Depends(require_view_reports),
    db: Session = Depends(get_db),
) -> Report:
    return _get_scoped(db, report_id, user)


@router.get("/{report_id}/versions", response_model=list[ReportVersionOut])
def list_versions(
    report_id: uuid.UUID,
    user: User = Depends(require_view_reports),
    db: Session = Depends(get_db),
) -> list[ReportVersion]:
    report = _get_scoped(db, report_id, user)
    stmt = (
        select(ReportVersion)
        .where(ReportVersion.report_id == report.id)
        .order_by(ReportVersion.version.desc())
    )
    return list(db.scalars(stmt))


def _next_version(db: Session, report_id: uuid.UUID) -> int:
    latest = db.scalar(
        select(ReportVersion.version)
        .where(ReportVersion.report_id == report_id)
        .order_by(ReportVersion.version.desc())
        .limit(1)
    )
    return (latest or 0) + 1


@router.patch("/{report_id}", response_model=ReportOut)
def update_report(
    report_id: uuid.UUID,
    body: ReportUpdateIn,
    request: Request,
    user: User = Depends(require(Permission.EDIT_REPORTS)),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_scoped(db, report_id, user)
    if report.status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Report is {report.status.value}, cannot be edited"
        )
    if body.title is not None:
        report.title = body.title
    if body.due_date is not None:
        report.due_date = body.due_date
    if body.content_json is not None:
        report.content_json = body.content_json
        db.add(
            ReportVersion(
                report_id=report.id,
                version=_next_version(db, report.id),
                content_json=body.content_json,
                edited_by=user.id,
                change_kind=ReportChangeKind.EDITED,
                change_comment=body.change_note,
            )
        )
    audit.record(
        db, "update_report", actor=user, entity="report", entity_id=report.id, request=request
    )
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/submit", response_model=ReportOut)
def submit_report(
    report_id: uuid.UUID,
    request: Request,
    user: User = Depends(require(Permission.EDIT_REPORTS)),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_scoped(db, report_id, user)
    if report.status not in _EDITABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Report is {report.status.value}, cannot be submitted"
        )
    report.status = ReportStatus.IN_REVIEW
    audit.record(
        db, "submit_report", actor=user, entity="report", entity_id=report.id, request=request
    )
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/approve", response_model=ReportOut)
def approve_report(
    report_id: uuid.UUID,
    request: Request,
    user: User = Depends(require(Permission.APPROVE_REPORTS)),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_scoped(db, report_id, user)
    if report.status != ReportStatus.IN_REVIEW:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Report is {report.status.value}, not awaiting approval"
        )
    report.status = ReportStatus.APPROVED
    report.approver_id = user.id
    db.add(
        ReportVersion(
            report_id=report.id,
            version=_next_version(db, report.id),
            content_json=report.content_json,
            edited_by=user.id,
            change_kind=ReportChangeKind.APPROVED,
        )
    )
    # So the approved reply is found by meaning, not only by its words (guide 10.2).
    similar_pq.remember(db, report)
    audit.record(
        db, "approve_report", actor=user, entity="report", entity_id=report.id, request=request
    )
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/reject", response_model=ReportOut)
def reject_report(
    report_id: uuid.UUID,
    body: RejectIn,
    request: Request,
    user: User = Depends(require(Permission.APPROVE_REPORTS)),
    db: Session = Depends(get_db),
) -> Report:
    report = _get_scoped(db, report_id, user)
    if report.status != ReportStatus.IN_REVIEW:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Report is {report.status.value}, not awaiting approval"
        )
    report.status = ReportStatus.RETURNED
    report.approver_id = user.id
    db.add(
        ReportVersion(
            report_id=report.id,
            version=_next_version(db, report.id),
            content_json=report.content_json,
            edited_by=user.id,
            change_kind=ReportChangeKind.RETURNED,
            change_comment=body.comment,  # the approver's words, shown exactly as typed
        )
    )
    audit.record(
        db,
        "reject_report",
        actor=user,
        entity="report",
        entity_id=report.id,
        details={"comment": body.comment},
        request=request,
    )
    db.commit()
    db.refresh(report)
    return report
