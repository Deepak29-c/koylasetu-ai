"""Home dashboard: one call that tells a person what needs their attention today."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, scope_to_user
from app.core.rbac import Permission, has_permission
from app.models import Document, Fact, QaLog, Report, User
from app.models.enums import DocumentStatus, FactStatus, ReportStatus
from app.schemas.dashboard import (
    ActivityPanelOut,
    DashboardSummaryOut,
    DocumentsPanelOut,
    ReportsPanelOut,
    ReviewPanelOut,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# A report is still someone's problem until it has been approved.
_OPEN_REPORT_STATUSES = (ReportStatus.DRAFT, ReportStatus.IN_REVIEW, ReportStatus.RETURNED)
DUE_SOON_DAYS = 7


def _count(db: Session, stmt: Select) -> int:
    return db.scalar(stmt) or 0


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _reports_panel(db: Session, user: User) -> ReportsPanelOut:
    def scoped() -> Select:
        return scope_to_user(select(func.count()).select_from(Report), Report, user)

    mine = scoped().where(Report.created_by == user.id)
    today = date.today()
    # Deadlines are only actionable by someone who can write or approve a report;
    # an export-only Viewer is not told about work they cannot move.
    acts_on_reports = has_permission(user.roles, Permission.EDIT_REPORTS) or has_permission(
        user.roles, Permission.APPROVE_REPORTS
    )
    open_and_dated = scoped().where(
        Report.status.in_(_OPEN_REPORT_STATUSES), Report.due_date.is_not(None)
    )

    def due(stmt: Select) -> int:
        return _count(db, stmt) if acts_on_reports else 0

    return ReportsPanelOut(
        my_drafts=_count(db, mine.where(Report.status == ReportStatus.DRAFT)),
        returned_to_me=_count(db, mine.where(Report.status == ReportStatus.RETURNED)),
        # Only an Approver can act on these, so only an Approver is told about them.
        awaiting_approval=(
            _count(db, scoped().where(Report.status == ReportStatus.IN_REVIEW))
            if has_permission(user.roles, Permission.APPROVE_REPORTS)
            else 0
        ),
        due_soon=due(
            open_and_dated.where(
                Report.due_date >= today, Report.due_date <= today + timedelta(days=DUE_SOON_DAYS)
            )
        ),
        overdue=due(open_and_dated.where(Report.due_date < today)),
    )


def _documents_panel(db: Session, user: User) -> DocumentsPanelOut:
    def scoped() -> Select:
        return scope_to_user(select(func.count()).select_from(Document), Document, user)

    return DocumentsPanelOut(
        processing=_count(
            db,
            scoped().where(
                Document.status.in_((DocumentStatus.UPLOADED, DocumentStatus.PROCESSING))
            ),
        ),
        needs_review=_count(db, scoped().where(Document.status == DocumentStatus.NEEDS_REVIEW)),
        failed=_count(db, scoped().where(Document.status == DocumentStatus.FAILED)),
        # updated_at is when the pipeline last touched the row, i.e. when it finished.
        processed_this_month=_count(
            db,
            scoped().where(
                Document.status == DocumentStatus.PROCESSED,
                Document.updated_at >= _month_start(),
            ),
        ),
    )


def _review_panel(db: Session, user: User) -> ReviewPanelOut:
    # Facts carry no org unit of their own; they inherit it from the document they came from.
    def scoped() -> Select:
        stmt = (
            select(func.count()).select_from(Fact).join(Document, Fact.document_id == Document.id)
        )
        return scope_to_user(stmt, Document, user)

    return ReviewPanelOut(
        pending_facts=_count(
            db, scoped().where(Fact.status.in_((FactStatus.EXTRACTED, FactStatus.FLAGGED)))
        ),
        flagged_facts=_count(db, scoped().where(Fact.status == FactStatus.FLAGGED)),
    )


def _activity_panel(db: Session, user: User) -> ActivityPanelOut:
    return ActivityPanelOut(
        questions_this_month=_count(
            db,
            select(func.count())
            .select_from(QaLog)
            .where(QaLog.user_id == user.id, QaLog.created_at >= _month_start()),
        )
    )


@router.get("/summary", response_model=DashboardSummaryOut)
def summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummaryOut:
    """Counts for the home page, filtered to what this person may see and act on.

    Every panel the caller lacks the permission for comes back as null rather than zero,
    so the frontend can tell "nothing to do" apart from "not your job".
    """

    def can(*permissions: Permission) -> bool:
        return any(has_permission(user.roles, p) for p in permissions)

    return DashboardSummaryOut(
        reports=(
            _reports_panel(db, user)
            if can(Permission.EDIT_REPORTS, Permission.APPROVE_REPORTS, Permission.EXPORT_REPORTS)
            else None
        ),
        documents=_documents_panel(db, user) if can(Permission.VIEW_PROCESSING) else None,
        review=_review_panel(db, user) if can(Permission.REVIEW_FACTS) else None,
        activity=_activity_panel(db, user) if can(Permission.ASK_QUESTIONS) else None,
    )
