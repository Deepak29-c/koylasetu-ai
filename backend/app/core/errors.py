"""Errors the browser can read (#69).

Two things here:

1. `CodedError`: an HTTP error that also carries a short `code` the frontend translates
   (`failure.<code>` in frontend/src/lib/i18n.tsx). The body is
   `{"detail": "<English sentence>", "code": "<code>"}`, so older clients that only read
   `detail` keep working.

2. `CatchUnhandledErrors`: a last-resort safety net. An exception nobody handled used to
   escape the whole middleware stack, Starlette answered 500 from outside CORSMiddleware,
   and the reply had no Access-Control-Allow-Origin header. The browser then refused to
   let the page read it and the frontend said "Cannot reach the KoylaSetu server" - while
   the server was up. This middleware sits *inside* CORSMiddleware (it is added before
   it; see main.py), turns the exception into a plain 500 with a generic message, and logs
   the traceback on the server. No exception text, class name or path goes to the browser.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger(__name__)

SERVER_ERROR_CODE = "server_error"
SERVER_ERROR_MESSAGE = (
    "Something went wrong on the server. Please try again; if it keeps happening, "
    "tell the administrator."
)


class CodedError(Exception):
    """An HTTP error with a translatable code alongside the English message."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code, self.code, self.detail = status_code, code, detail


async def _coded_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, CodedError)
    return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=exc.status_code)


class CatchUnhandledErrors:
    """Pure ASGI middleware: any unhandled exception becomes a generic JSON 500."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_tracking(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking)
        except Exception:
            log.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:  # half a response is already out; nothing sensible left to send
                raise
            response = JSONResponse(
                {"detail": SERVER_ERROR_MESSAGE, "code": SERVER_ERROR_CODE}, status_code=500
            )
            await response(scope, receive, send)


def install(app: FastAPI) -> None:
    """Register both. Call this BEFORE adding CORSMiddleware, so CORS wraps the safety net
    and even a 500 carries the CORS headers."""
    app.add_exception_handler(CodedError, _coded_error)
    app.add_middleware(CatchUnhandledErrors)
