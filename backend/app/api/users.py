import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require, scope_to_user
from app.core.rbac import Permission
from app.core.security import hash_password
from app.models import OrgUnit, User
from app.schemas.auth import OrgUnitOut
from app.schemas.user import UserCreateIn, UserOut, UserUpdateIn
from app.services import audit

router = APIRouter(tags=["users"])


@router.get("/org-units", response_model=list[OrgUnitOut])
def list_org_units(
    _: User = Depends(require(Permission.MANAGE_ADMIN)),
    db: Session = Depends(get_db),
) -> list[OrgUnit]:
    return list(db.scalars(select(OrgUnit).order_by(OrgUnit.name)))


@router.get("/users", response_model=list[UserOut])
def list_users(
    user: User = Depends(require(Permission.MANAGE_ADMIN)),
    db: Session = Depends(get_db),
) -> list[User]:
    stmt = scope_to_user(select(User), User, user).order_by(User.name)
    return list(db.scalars(stmt))


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateIn,
    request: Request,
    user: User = Depends(require(Permission.MANAGE_ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    if db.scalar(select(User).where(User.email == body.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    if db.get(OrgUnit, body.org_unit_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No such org unit")
    new_user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        roles=body.roles,
        org_unit_id=body.org_unit_id,
        is_active=True,
    )
    db.add(new_user)
    db.flush()
    audit.record(
        db,
        "create_user",
        user_id=user.id,
        entity="user",
        entity_id=new_user.id,
        details={"email": new_user.email, "roles": new_user.roles},
        request=request,
    )
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdateIn,
    request: Request,
    user: User = Depends(require(Permission.MANAGE_ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    target = db.scalar(scope_to_user(select(User).where(User.id == user_id), User, user))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.id == user.id and body.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
    if body.org_unit_id is not None and db.get(OrgUnit, body.org_unit_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No such org unit")

    changes: dict[str, object] = {}
    for field in ("name", "roles", "org_unit_id", "is_active"):
        value = getattr(body, field)
        if value is not None and value != getattr(target, field):
            changes[field] = str(value) if isinstance(value, uuid.UUID) else value
            setattr(target, field, value)

    if changes:
        audit.record(
            db,
            "update_user",
            user_id=user.id,
            entity="user",
            entity_id=target.id,
            details=changes,
            request=request,
        )
        db.commit()
        db.refresh(target)
    return target
