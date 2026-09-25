import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(
    db: Session,
    action: str,
    *,
    actor: User | None,
    org_unit_id: uuid.UUID | None = None,
    entity: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> None:
    """Add an audit row to the session. The caller commits.

    `actor` sets both who did it and which unit's audit log it lands in. It takes the
    user rather than their id on purpose: a new call site cannot then forget the unit
    and silently write a row that only CIL HQ can ever read.

    Pass `org_unit_id` on its own for an action that belongs to a unit but has no actor
    to attribute it to — a failed login against a known account, for example.
    """
    db.add(
        AuditLog(
            user_id=actor.id if actor else None,
            org_unit_id=actor.org_unit_id if actor else org_unit_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details_json=details,
            ip=request.client.host if request and request.client else None,
        )
    )
