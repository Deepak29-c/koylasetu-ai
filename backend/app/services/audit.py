import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    action: str,
    *,
    user_id: uuid.UUID | None,
    entity: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> None:
    """Add an audit row to the session. The caller commits."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details_json=details,
            ip=request.client.host if request and request.client else None,
        )
    )
