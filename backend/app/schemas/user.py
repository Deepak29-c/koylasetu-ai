import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.rbac import Role
from app.schemas.auth import OrgUnitOut

VALID_ROLES = {r.value for r in Role}


def _check_roles(roles: list[str]) -> list[str]:
    if not roles:
        raise ValueError("At least one role is required")
    unknown = set(roles) - VALID_ROLES
    if unknown:
        raise ValueError(f"Unknown role(s): {', '.join(sorted(unknown))}")
    return roles


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    roles: list[str]
    org_unit: OrgUnitOut
    is_active: bool
    created_at: datetime


class UserCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    roles: list[str]
    org_unit_id: uuid.UUID

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str]) -> list[str]:
        return _check_roles(v)


class UserUpdateIn(BaseModel):
    """Every field is optional: send only what you want to change."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    roles: list[str] | None = None
    org_unit_id: uuid.UUID | None = None
    is_active: bool | None = None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str] | None) -> list[str] | None:
        return _check_roles(v) if v is not None else v
