"""Monthly report and briefing note first drafts (guide 10.1, workflows W5 and W6).

POST /reports/monthly/draft   {month, subsidiaries?}  -> DRAFT monthly report
POST /reports/briefing/draft  {topic, from?, to?}     -> DRAFT briefing note

Both are saved like a PQ reply draft: a DRAFT report with its first version, one
report_citations row per fact / chunk used, and an audit entry. They are then edited,
submitted and approved in the reports screens (app.api.reports) and exported with
GET /reports/{id}/export (app.api.pq_replies). Nothing is sent anywhere.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.pq_replies import MODEL_DOWN, _same_request
from app.core.db import get_db
from app.core.deps import require
from app.core.rbac import Permission
from app.llm.client import LlmUnavailable
from app.models import Report, ReportCitation, ReportVersion, User
from app.models.enums import ReportStatus, ReportType
from app.schemas.report_draft import BriefingDraftIn, MonthlyDraftIn, ReportDraftOut
from app.services import audit, briefing_note, monthly_report

log = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def _save(
    db: Session,
    user: User,
    request: Request,
    *,
    report_type: ReportType,
    title: str,
    content: dict,
    links: list[dict],
    idempotency_key: str | None,
    action: str,
    details: dict,
) -> Report:
    if idempotency_key:
        content = content | {"idempotency_key": idempotency_key}
    report = Report(
        report_type=report_type,
        title=title[:500],
        status=ReportStatus.DRAFT,
        content_json=content,
        org_unit_id=user.org_unit_id,
        created_by=user.id,
    )
    db.add(report)
    db.flush()
    db.add(
        ReportVersion(
            report_id=report.id,
            version=1,
            content_json=content,
            edited_by=user.id,
            change_note="First draft generated",
        )
    )
    for link in links:
        db.add(ReportCitation(report_id=report.id, **link))
    audit.record(
        db,
        action,
        actor=user,
        entity="report",
        entity_id=report.id,
        details=details | {"sources": len(content.get("sources") or []), "links": len(links)},
        request=request,
    )
    db.commit()
    db.refresh(report)
    return report


@router.post("/monthly/draft", response_model=ReportDraftOut, status_code=status.HTTP_201_CREATED)
def create_monthly_draft(
    body: MonthlyDraftIn,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, max_length=64),
    user: User = Depends(require(Permission.EDIT_REPORTS)),
    db: Session = Depends(get_db),
) -> ReportDraftOut:
    existing = _same_request(db, user, idempotency_key)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return ReportDraftOut(report=existing)
    draft = monthly_report.draft_monthly(db, user, body.month, codes=body.subsidiaries)
    existing = _same_request(db, user, idempotency_key)  # a retry may have finished first
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return ReportDraftOut(report=existing)
    content = draft.content
    report = _save(
        db,
        user,
        request,
        report_type=ReportType.MONTHLY,
        title=f"Monthly report - {monthly_report.month_name(body.month)}",
        content=content,
        links=draft.links,
        idempotency_key=idempotency_key,
        action="create_monthly_draft",
        details={
            "month": body.month,
            "subsidiaries": body.subsidiaries,
            "facts_used": content["facts_used"],
            "cells_not_found": content["cells_not_found"],
            "remarks_by": content["remarks_by"],
            "figures_removed": sum(len(s["removed_numbers"]) for s in content["sections"]),
        },
    )
    return ReportDraftOut(report=report)


@router.post("/briefing/draft", response_model=ReportDraftOut, status_code=status.HTTP_201_CREATED)
def create_briefing_draft(
    body: BriefingDraftIn,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, max_length=64),
    user: User = Depends(require(Permission.EDIT_REPORTS)),
    db: Session = Depends(get_db),
) -> ReportDraftOut:
    existing = _same_request(db, user, idempotency_key)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return ReportDraftOut(report=existing)
    try:
        draft = briefing_note.draft_briefing(
            db, user, body.topic, start=body.from_month, end=body.to_month
        )
    except LlmUnavailable as e:
        log.warning("Briefing draft failed, model unavailable: %s", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, MODEL_DOWN) from None
    existing = _same_request(db, user, idempotency_key)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return ReportDraftOut(report=existing)
    content = draft.content
    report = _save(
        db,
        user,
        request,
        report_type=ReportType.BRIEFING,
        title=f"Briefing note: {body.topic.strip()}",
        content=content,
        links=draft.links,
        idempotency_key=idempotency_key,
        action="create_briefing_draft",
        details={
            "topic": body.topic.strip()[:200],
            "from": body.from_month,
            "to": body.to_month,
            "metrics": content["metrics"],
            "subsidiaries": content["subsidiaries"],
            "points_not_found": content["points_not_found"],
            "figures_removed": sum(len(s["removed_numbers"]) for s in content["sections"]),
        },
    )
    return ReportDraftOut(report=report)
