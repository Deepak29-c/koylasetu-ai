import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    csrf_refused,
    has_csrf_header,
    set_auth_cookies,
)
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.rbac import Permission, has_permission
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import ChangePasswordIn, LoginIn, MeOut, RefreshIn, TokenOut
from app.services import audit

router = APIRouter(tags=["auth"])


def _issue(user: User, response: Response) -> TokenOut:
    """New tokens as httpOnly cookies for the browser, and in the body for scripts."""
    tokens = TokenOut(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post("/auth/login", response_model=TokenOut)
def login(
    body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)
) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        audit.record(
            db,
            "login_failed",
            actor=None,
            org_unit_id=user.org_unit_id if user else None,
            details={"email": body.email},
            request=request,
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    audit.record(db, "login", actor=user, entity="user", entity_id=user.id, request=request)
    db.commit()
    return _issue(user, response)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(
    request: Request,
    response: Response,
    body: RefreshIn | None = None,
    db: Session = Depends(get_db),
) -> TokenOut:
    """Scripts send the refresh token in the body; the browser sends its refresh cookie."""
    expired = HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    if body is not None:
        token = body.refresh_token
    else:
        token = request.cookies.get(REFRESH_COOKIE)
        if token is None:
            raise expired
        if not has_csrf_header(request):
            raise csrf_refused()
    try:
        user_id = decode_token(token, "refresh")
    except jwt.InvalidTokenError:
        raise expired from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise expired
    return _issue(user, response)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Remove the login cookies. Needs no valid session, so an expired one can still leave."""
    clear_auth_cookies(response)


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


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is wrong")
    user.password_hash = hash_password(body.new_password)
    audit.record(
        db, "change_password", actor=user, entity="user", entity_id=user.id, request=request
    )
    db.commit()
