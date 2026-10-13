"""Settings read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    gemini_embed_model: str
    ner_model_dir: str
    session_ttl_seconds: int
    max_sessions: int
    max_upload_bytes: int
    max_text_chars: int
    cookie_secure: bool


def load_settings() -> Settings:
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        gemini_embed_model=os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001"),
        # Trained name recognizer; without it the rules alone are used. Empty string turns it off.
        ner_model_dir=os.environ.get("NER_MODEL_DIR", "models/ner"),
        session_ttl_seconds=_int("SESSION_TTL_SECONDS", 30 * 60),
        max_sessions=_int("MAX_SESSIONS", 200),
        max_upload_bytes=_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
        # The real cost limit: ~80-100 pages of text (memory per session and embedding requests).
        max_text_chars=_int("MAX_TEXT_CHARS", 200_000),
        # Local development over plain http needs COOKIE_SECURE=0.
        cookie_secure=os.environ.get("COOKIE_SECURE", "1") != "0",
    )
