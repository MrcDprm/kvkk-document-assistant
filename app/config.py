"""Settings read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    session_ttl_seconds: int
    max_sessions: int
    max_upload_bytes: int
    cookie_secure: bool


def load_settings() -> Settings:
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        session_ttl_seconds=_int("SESSION_TTL_SECONDS", 30 * 60),
        max_sessions=_int("MAX_SESSIONS", 200),
        max_upload_bytes=_int("MAX_UPLOAD_BYTES", 2 * 1024 * 1024),
        # Local development over plain http needs COOKIE_SECURE=0.
        cookie_secure=os.environ.get("COOKIE_SECURE", "1") != "0",
    )
