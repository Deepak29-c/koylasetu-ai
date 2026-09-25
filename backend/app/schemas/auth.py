import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginIn(BaseModel):
    # Plain string, not EmailStr: EmailStr rejects reserved domains such as the demo
    # users' "@koylasetu.local". Login only needs an exact match against stored emails.
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalise(cls, v: str) -> str:
        return v.strip().lower()


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class OrgUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    type: str


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    roles: list[str]
    org_unit: OrgUnitOut
    permissions: list[str]
