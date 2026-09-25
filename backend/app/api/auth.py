import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.rbac import Permission, has_permission
from app.core.security import create_token, decode_token, verify_password
from app.models import User
from app.schemas.auth import LoginIn, MeOut, RefreshIn, TokenOut
from app.services import audit

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        audit.record(
            db, "login_failed", user_id=None, details={"email": body.email}, request=request
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    audit.record(db, "login", user_id=user.id, entity="user", entity_id=user.id, request=request)
    db.commit()
    return TokenOut(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)) -> TokenOut:
    try:
        user_id = decode_token(body.refresh_token, "refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    return TokenOut(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        roles=user.roles,
        org_unit=user.org_unit,
        permissions=[p.value for p in Permission if has_permission(user.roles, p)],
    )
