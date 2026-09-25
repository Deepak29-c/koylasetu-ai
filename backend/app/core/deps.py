"""FastAPI dependencies: current user, permission checks, org-unit scoping."""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, or_
from sqlalchemy.orm import Session

from app.core.cookies import ACCESS_COOKIE, SAFE_METHODS, csrf_refused, has_csrf_header
from app.core.db import get_db
from app.core.rbac import ALL_SCOPE_ORG_CODES, Permission, has_permission
from app.core.security import decode_token
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """The logged-in user, from a Bearer header (scripts) or the access cookie (browser).

    A cookie-authenticated request that changes something must carry CSRF_HEADER; see
    app/core/cookies.py for why.
    """
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not logged in", {"WWW-Authenticate": "Bearer"}
    )
    if creds is not None:
        token = creds.credentials
    else:
        token = request.cookies.get(ACCESS_COOKIE)
        if token is None:
            raise unauthorized
        if request.method not in SAFE_METHODS and not has_csrf_header(request):
            raise csrf_refused()
    try:
        user_id = decode_token(token, "access")
    except jwt.InvalidTokenError:
        raise unauthorized from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require(permission: Permission) -> Callable[..., User]:
    """Use as `user: User = Depends(require(Permission.X))` on every endpoint."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.roles, permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot do this")
        return user

    return checker


def sees_all_units(user: User) -> bool:
    return user.org_unit.code in ALL_SCOPE_ORG_CODES


def scope_to_user(stmt: Select, model: type, user: User) -> Select:
    """Filter a query to the user's org unit (guide section 2). Apply on EVERY data query.

    CIL HQ and Ministry users see everything. Others see their own unit, plus rows marked
    public when the model has an `is_public` column.
    """
    if sees_all_units(user):
        return stmt
    condition = model.org_unit_id == user.org_unit_id
    if hasattr(model, "is_public"):
        condition = or_(condition, model.is_public.is_(True))
    return stmt.where(condition)
