"""Similar past Parliament questions (guide section 10.2, "similar past questions" panel).

GET /pq/similar?text=...&limit=5   any logged-in user; results scoped to their org unit.

Approved replies are included only for users who may read reports, since each result links
to one. Uploaded PQ answers are documents and are open to every role.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.rbac import Permission, has_permission
from app.models import User
from app.schemas.similar_pq import SimilarPqOut
from app.services import similar_pq

router = APIRouter(prefix="/pq", tags=["pq-replies"])

REPORT_VIEW_PERMISSIONS = (
    Permission.EDIT_REPORTS,
    Permission.APPROVE_REPORTS,
    Permission.EXPORT_REPORTS,
)


def may_read_reports(user: User) -> bool:
    return any(has_permission(user.roles, p) for p in REPORT_VIEW_PERMISSIONS)


@router.get("/similar", response_model=list[SimilarPqOut])
def similar(
    text: str = Query("", max_length=similar_pq.MAX_TEXT * 2),
    limit: int = Query(5, ge=1, le=20),
    exclude: uuid.UUID | None = Query(None, description="a report to leave out (the one open)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[similar_pq.Similar]:
    return similar_pq.find_similar(
        db,
        user,
        text,
        limit=limit,
        include_replies=may_read_reports(user),
        exclude=exclude,
    )
