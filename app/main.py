"""FastAPI application: app factory, security headers and error handling."""

import logging
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartParser
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings, load_settings
from app.llm import LLM, GeminiLLM
from app.ratelimit import RateLimiter
from app.store import SessionStore
from app.web import render, router

logger = logging.getLogger("kvkk")

SECURITY_HEADERS = {
    # Only our own files may run or load; no inline scripts, no framing.
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    # "no-referrer" would make browsers send "Origin: null" on our own form posts.
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # Pages show personal data: browsers and proxies must not keep a copy.
    "Cache-Control": "no-store",
}

RATE_LIMITS = {
    "analyze": (20, 10 * 60),  # 20 documents per 10 minutes
    "toggle": (300, 60),
    "ask": (15, 10 * 60),  # each question costs free-tier quota
}

# Starlette writes uploads above 1 MB to a temporary file on disk. Documents must never touch
# the disk, so uploads stay in memory; BodySizeLimit below keeps that memory bounded.
MultiPartParser.spool_max_size = 16 * 1024 * 1024


class BodyTooLarge(Exception):
    pass


class BodySizeLimit:
    """Reject request bodies above `max_bytes` before they are read into memory."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope["headers"])
        declared = headers.get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            return await self._too_large(scope, receive, send)

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except BodyTooLarge:
            await self._too_large(scope, receive, send)

    async def _too_large(self, scope: Scope, receive: Receive, send: Send) -> None:
        # A form post gets the home page with a message; anything else a plain 413.
        if scope["path"] == "/analyze":
            response = RedirectResponse("/?error=too_large", status_code=303)
        else:
            response = Response(status_code=413)
        await response(scope, receive, send)


def create_app(settings: Settings | None = None, llm: LLM | None = None) -> FastAPI:
    """`llm` lets tests pass a fake model; without a key, asking questions is turned off."""
    settings = settings or load_settings()
    # The interactive API docs are not needed in production.
    app = FastAPI(title="KVKK Document Assistant", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.store = SessionStore(settings.session_ttl_seconds, settings.max_sessions)
    app.state.limiter = RateLimiter(RATE_LIMITS)
    if llm is None and settings.gemini_api_key:
        llm = GeminiLLM(settings.gemini_api_key, settings.gemini_model, settings.gemini_embed_model)
    app.state.llm = llm

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.middleware("http")
    async def same_origin_posts(request: Request, call_next) -> Response:
        # Second CSRF defence next to SameSite cookies: a POST from another site is refused.
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
            if urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"error": "forbidden"}, status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404 and not request.url.path.startswith("/api/"):
            return render(request, "404.html", status_code=404)
        if exc.status_code == 400 and request.url.path == "/analyze":
            # Malformed or oversized form fields (e.g. a pasted text far above the limit).
            return RedirectResponse("/?error=too_large", status_code=303)
        return JSONResponse({"error": "http_error"}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Log the details on the server; the user only gets a generic message (no stack trace).
        logger.exception("Unhandled error on %s", request.url.path)
        # This handler runs outside the middleware above, so the headers are added here too.
        return JSONResponse({"error": "internal_error"}, status_code=500, headers=SECURITY_HEADERS)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    # Added last, so it is the outermost of our middlewares. 256 KB covers the multipart overhead.
    app.add_middleware(BodySizeLimit, max_bytes=settings.max_upload_bytes + 256 * 1024)
    return app


app = create_app()
