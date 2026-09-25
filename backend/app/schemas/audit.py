import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    user: AuditUserOut | None
    action: str
    entity: str | None
    entity_id: str | None
    details_json: dict | None
    ip: str | None
