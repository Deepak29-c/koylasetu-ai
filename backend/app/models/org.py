import uuid

from sqlalchemy import ARRAY, Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Entity, str_enum
from app.models.enums import OrgType


class OrgUnit(Entity):
    __tablename__ = "org_units"

    code: Mapped[str] = mapped_column(String(16), unique=True)  # CMPDI, ECL, ..., CIL_HQ, MINISTRY
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[OrgType] = mapped_column(str_enum(OrgType, "org_type"))


class User(Entity):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # A list because one person can hold several roles (guide section 2), e.g. analyst + approver.
    # Values are app.core.rbac.Role.
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    org_unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org_units.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    org_unit: Mapped[OrgUnit] = relationship(lazy="joined")
