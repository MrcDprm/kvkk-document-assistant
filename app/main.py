"""FastAPI application: app factory, security headers and error handling."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.config import Settings, load_settings
from app.store import SessionStore

logger = logging.getLogger("kvkk")

SECURITY_HEADERS = {
    # Only our own files may run or load; no inline scripts, no framing.
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # Pages show personal data: browsers and proxies must not keep a copy.
    "Cache-Control": "no-store",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    # The interactive API docs are not needed in production.
    app = FastAPI(title="KVKK Document Assistant", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.store = SessionStore(settings.session_ttl_seconds, settings.max_sessions)

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Log the details on the server; the user only gets a generic message (no stack trace).
        logger.exception("Unhandled error on %s", request.url.path)
        # This handler runs outside the middleware above, so the headers are added here too.
        return JSONResponse({"error": "internal_error"}, status_code=500, headers=SECURITY_HEADERS)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
