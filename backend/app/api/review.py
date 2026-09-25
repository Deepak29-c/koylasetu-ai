"""Review queue (guide W2): flagged facts, Accept / Edit / Reject, audit trail."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require, scope_to_user
from app.core.rbac import Permission
from app.models import Document, Fact, ReviewActionLog, User, ValidationIssue
from app.models.enums import DocumentStatus, FactStatus, IssueStatus, ReviewAction, Severity
from app.schemas.review import (
    FactOut,
    IssueOut,
    RelatedFactOut,
    ReviewDecision,
    ReviewItem,
    ReviewSummary,
)
from app.services import audit
from app.services.normalise import parse_number

router = APIRouter(prefix="/review", tags=["review"])

_SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


def _scoped_fact(db: Session, fact_id: uuid.UUID, user: User) -> tuple[Fact, Document]:
    row = db.execute(
        scope_to_user(
            select(Fact, Document)
            .join(Document, Document.id == Fact.document_id)
            .where(Fact.id == fact_id),
            Document,
            user,
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fact not found")
    return row


@router.get("/issues", response_model=list[ReviewItem])
def review_queue(
    document_id: uuid.UUID | None = None,
    severity: Severity | None = None,
    rule: str | None = Query(None, pattern=r"^V0[1-8]$"),
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(require(Permission.REVIEW_FACTS)),
    db: Session = Depends(get_db),
) -> list[ReviewItem]:
    """Flagged facts that still have open issues, worst first."""
    stmt = (
        select(ValidationIssue, Fact, Document.title)
        .join(Fact, Fact.id == ValidationIssue.fact_id)
        .join(Document, Document.id == Fact.document_id)
        .where(ValidationIssue.status == IssueStatus.OPEN)
    )
    if document_id:
        stmt = stmt.where(Fact.document_id == document_id)
    if severity:
        stmt = stmt.where(ValidationIssue.severity == severity)
    if rule:
        stmt = stmt.where(ValidationIssue.rule_code == rule)
    rows = db.execute(scope_to_user(stmt, Document, user)).all()

    items: dict[uuid.UUID, dict] = {}
    related_ids: set[uuid.UUID] = set()
    for issue, fact, title in rows:
        item = items.setdefault(fact.id, {"fact": fact, "title": title, "issues": []})
        item["issues"].append(issue)
        if issue.related_fact_id:
            related_ids.add(issue.related_fact_id)

    related: dict[uuid.UUID, RelatedFactOut] = {}
    if related_ids:
        for f, t in db.execute(
            scope_to_user(
                select(Fact, Document.title)
                .join(Document, Document.id == Fact.document_id)
                .where(Fact.id.in_(related_ids)),
                Document,
                user,
            )
        ).all():
            related[f.id] = RelatedFactOut(
                **FactOut.model_validate(f).model_dump(), document_title=t
            )

    out = []
    for item in items.values():
        issues = sorted(item["issues"], key=lambda i: _SEVERITY_ORDER[i.severity])
        out.append(
            ReviewItem(
                fact=FactOut.model_validate(item["fact"]),
                document_title=item["title"],
                issues=[IssueOut.model_validate(i) for i in issues],
                related=[
                    related[i.related_fact_id] for i in issues if i.related_fact_id in related
                ],
                worst_severity=issues[0].severity.value,
                created_at=issues[0].created_at,
            )
        )
    out.sort(key=lambda r: (_SEVERITY_ORDER[Severity(r.worst_severity)], r.created_at))
    return out[:limit]


@router.post("/facts/{fact_id}", response_model=FactOut)
def decide(
    fact_id: uuid.UUID,
    body: ReviewDecision,
    request: Request,
    user: User = Depends(require(Permission.REVIEW_FACTS)),
    db: Session = Depends(get_db),
) -> Fact:
    fact, doc = _scoped_fact(db, fact_id, user)
    old = f"{fact.value}"
    new = None
    if body.action == "EDIT":
        value = parse_number(body.new_value or "")
        if value is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a number")
        # keep the unit: the standard value scales with the corrected original-unit value
        # (no standard value = the unit could not be converted; it stays unconverted)
        if fact.value_std is not None:
            factor = float(fact.value_std) / float(fact.value) if fact.value else 1
            fact.value_std = round(value * factor, 6)
        fact.value = value
        new = f"{value}"
    fact.status = FactStatus.REJECTED if body.action == "REJECT" else FactStatus.VERIFIED

    for issue in db.scalars(
        select(ValidationIssue).where(
            ValidationIssue.fact_id == fact.id, ValidationIssue.status == IssueStatus.OPEN
        )
    ):
        issue.status = IssueStatus.RESOLVED
    db.add(
        ReviewActionLog(
            fact_id=fact.id,
            user_id=user.id,
            action=ReviewAction(body.action),
            old_value=old,
            new_value=new,
            comment=body.comment,
        )
    )
    audit.record(
        db, f"review_{body.action.lower()}", actor=user, entity="fact", entity_id=fact.id,
        details={"old": old, "new": new, "comment": body.comment, "label": fact.label},
        request=request,
    )  # fmt: skip
    db.flush()

    still_open = db.scalar(
        select(
            exists().where(
                ValidationIssue.fact_id == Fact.id,
                Fact.document_id == doc.id,
                ValidationIssue.status == IssueStatus.OPEN,
            )
        )
    )
    if not still_open and doc.status == DocumentStatus.NEEDS_REVIEW:
        doc.status = DocumentStatus.PROCESSED
    db.commit()
    return fact


@router.get("/summary", response_model=ReviewSummary)
def summary(
    user: User = Depends(require(Permission.REVIEW_FACTS)),
    db: Session = Depends(get_db),
) -> ReviewSummary:
    reviewed = exists().where(ReviewActionLog.fact_id == Fact.id)
    stmt = select(
        func.count(),
        func.count().filter(Fact.status == FactStatus.VERIFIED, ~reviewed),
        func.count().filter(Fact.status == FactStatus.FLAGGED),
        func.count().filter(Fact.status == FactStatus.VERIFIED, reviewed),
        func.count().filter(Fact.status == FactStatus.REJECTED),
    ).join(Document, Document.id == Fact.document_id)
    total, auto, flagged, human, rejected = db.execute(scope_to_user(stmt, Document, user)).one()
    return ReviewSummary(
        total_facts=total,
        auto_verified=auto,
        flagged=flagged,
        reviewed_verified=human,
        rejected=rejected,
        automation_percent=round(100 * auto / total, 1) if total else None,
    )
