"""Settings read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _list(name: str, default: str) -> list[str]:
    """A comma-separated environment variable."""
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_models: list[str]
    gemini_embed_model: str
    groq_api_key: str
    groq_model: str
    ner_model_dir: str
    ner_threads: int
    allowed_hosts: list[str]
    session_ttl_seconds: int
    max_sessions: int
    max_upload_bytes: int
    max_text_chars: int
    cookie_secure: bool


def load_settings() -> Settings:
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        # Tried in this order after Groq; each model has its own free daily quota.
        gemini_models=_list("GEMINI_MODELS", "gemini-2.5-flash,gemini-3.1-flash-lite"),
        gemini_embed_model=os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001"),
        groq_api_key=os.environ.get("GROQ_API_KEY", "").strip(),
        groq_model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        # Trained name recognizer; without it the rules alone are used. Empty string turns it off.
        ner_model_dir=os.environ.get("NER_MODEL_DIR", "models/ner"),
        # The free server has 0.1 CPU: more threads would only add overhead there.
        ner_threads=_int("NER_THREADS", 1),
        # Host names the app answers to (Host header check); comma separated.
        allowed_hosts=_list("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"),
        session_ttl_seconds=_int("SESSION_TTL_SECONDS", 30 * 60),
        max_sessions=_int("MAX_SESSIONS", 200),
        max_upload_bytes=_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
        # The real limit: ~40 pages. The name model reads ~2,500 characters per second on the
        # free 0.1 CPU server, so this keeps the slowest analysis around 40 seconds.
        max_text_chars=_int("MAX_TEXT_CHARS", 100_000),
        # Local development over plain http needs COOKIE_SECURE=0.
        cookie_secure=os.environ.get("COOKIE_SECURE", "1") != "0",
    )
