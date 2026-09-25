"""Login cookies for the browser (guide section 14).

The web app keeps no token in page storage: the API sets both tokens as httpOnly cookies,
so page scripts cannot read them. The access cookie goes with every request; the refresh
cookie only with /auth/* (its path), which is where it is needed.

Cookies are sent by the browser on their own, so a request authenticated by the access
cookie must also carry CSRF_HEADER when it changes something (see deps.get_current_user).
A plain cross-site form cannot set a custom header, and a cross-site script that tries
needs a CORS preflight, which only the configured origins pass. Scripts that send a
Bearer header are not affected.
"""

from fastapi import HTTPException, Request, Response, status

from app.core.config import get_settings

ACCESS_COOKIE = "ks_access"
REFRESH_COOKIE = "ks_refresh"
REFRESH_COOKIE_PATH = "/auth"

CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "koylasetu"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    s = get_settings()
    common = {"httponly": True, "samesite": "lax", "secure": s.cookie_secure}
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=s.access_token_minutes * 60, path="/", **common
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=s.refresh_token_days * 86400,
        path=REFRESH_COOKIE_PATH,
        **common,
    )


def clear_auth_cookies(response: Response) -> None:
    s = get_settings()
    common = {"httponly": True, "samesite": "lax", "secure": s.cookie_secure}
    response.delete_cookie(ACCESS_COOKIE, path="/", **common)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, **common)


def has_csrf_header(request: Request) -> bool:
    return request.headers.get(CSRF_HEADER) == CSRF_VALUE


def csrf_refused() -> HTTPException:
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"Request refused: a browser request that changes data must send the "
        f"{CSRF_HEADER}: {CSRF_VALUE} header",
    )
