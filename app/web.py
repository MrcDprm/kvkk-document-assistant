"""Pages and JSON endpoints for uploading a document and reviewing the masking."""

import secrets
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile

from app.extract import ExtractError, extract_text, normalize_text
from app.i18n import JS_KEYS, LANG_COOKIE, LANGS, TEXTS, get_lang, translator
from app.store import Session
from kvkk_mask import detect
from kvkk_mask.fakegen import TEMPLATES, make_document

SESSION_COOKIE = "kvkk_session"

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter()


def render(request: Request, name: str, status_code: int = 200, **context) -> Response:
    lang = get_lang(request)
    return templates.TemplateResponse(
        request,
        name,
        {"lang": lang, "t": translator(lang), "demo_kinds": list(TEMPLATES), **context},
        status_code=status_code,
    )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def current_session(request: Request) -> Session | None:
    return request.app.state.store.get(request.cookies.get(SESSION_COOKIE))


# --- Pages ---

@router.get("/")
def home(request: Request, error: str = "") -> Response:
    # Only known error codes are shown; anything else in the URL is ignored.
    known = f"error.{error}" in TEXTS["tr"]
    return render(request, "home.html", error=error if known else "")


@router.post("/analyze")
async def analyze(request: Request) -> Response:
    settings = request.app.state.settings
    if not request.app.state.limiter.allow("analyze", client_ip(request)):
        return render(request, "home.html", status_code=429, error="rate_limited")

    form = await request.form(max_files=1, max_fields=5)
    mode = form.get("mode", "file")
    pasted = form.get("text", "") if isinstance(form.get("text"), str) else ""
    try:
        if mode == "text":
            filename, text = "", normalize_text(pasted, settings.max_text_chars)
        elif mode == "demo":
            kind = form.get("demo")
            kind = kind if kind in TEMPLATES else next(iter(TEMPLATES))
            filename, text = f"demo-{kind}.txt", make_document(kind, seed=secrets.randbelow(10**9)).text
        else:
            upload = form.get("file")
            if not isinstance(upload, UploadFile) or not upload.filename:
                raise ExtractError("no_file")
            data = await upload.read(settings.max_upload_bytes + 1)
            filename = Path(upload.filename).name[:120]
            text = extract_text(filename, data, settings.max_upload_bytes, settings.max_text_chars)
    except ExtractError as e:
        return render(request, "home.html", status_code=400, error=e.code, mode=mode, pasted=pasted)

    store = request.app.state.store
    old = request.cookies.get(SESSION_COOKIE)
    if old:
        store.delete(old)  # one document per visitor: the previous one is dropped from memory
    session = store.create()
    session.filename = filename
    session.text = text
    session.entities = detect(text)
    session.pseudonymizer.mask(text, session.entities)  # assign tokens in document order

    response = RedirectResponse("/document", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        session.id,
        httponly=True,  # JavaScript cannot read the session id
        secure=settings.cookie_secure,
        samesite="lax",  # not sent on cross-site POSTs (CSRF)
        max_age=settings.session_ttl_seconds,
    )
    return response


@router.get("/document")
def document_page(request: Request) -> Response:
    if current_session(request) is None:
        return RedirectResponse("/?error=expired" if request.cookies.get(SESSION_COOKIE) else "/", status_code=303)
    t = translator(get_lang(request))
    return render(request, "document.html", js_texts={k: t(k) for k in JS_KEYS})


@router.post("/reset")
def reset(request: Request) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        request.app.state.store.delete(session_id)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/lang/{code}")
def set_lang(code: str, next: str = "/") -> Response:
    # Only local paths: "//evil.com" or "https://..." would be an open redirect.
    target = next if next.startswith("/") and not next.startswith("//") and "\\" not in next else "/"
    response = RedirectResponse(target, status_code=303)
    if code in LANGS:
        response.set_cookie(LANG_COOKIE, code, max_age=365 * 24 * 3600, samesite="lax", httponly=True)
    return response


# --- JSON for the document view ---

def document_payload(session: Session) -> dict:
    """The document split into plain and highlighted segments, plus one row per pseudonym.

    Segments (instead of character offsets) are sent because JavaScript counts string
    positions differently from Python for some characters (e.g. emoji).
    """
    p = session.pseudonymizer
    text = session.text
    original: list[dict] = []
    masked: list[dict] = []
    findings: dict[str, dict] = {}  # token -> row, in order of first mention
    pos = 0

    for e in session.entities:
        token = p.token_for(e)
        excluded = token in session.excluded
        row = findings.setdefault(token, {
            "key": token.strip("[]"),
            "token": token,
            "type": e.type.value,
            "text": e.text,
            "count": 0,
            "excluded": excluded,
        })
        row["count"] += 1

        if e.start > pos:
            plain = {"text": text[pos:e.start]}
            original.append(plain)
            masked.append(plain)
        original.append({"text": e.text, "type": e.type.value, "excluded": excluded})
        masked.append({"text": e.text} if excluded else {"text": token, "type": e.type.value})
        pos = e.end
    if pos < len(text):
        original.append({"text": text[pos:]})
        masked.append({"text": text[pos:]})

    counts: dict[str, int] = {}
    for row in findings.values():
        if not row["excluded"]:
            counts[row["type"]] = counts.get(row["type"], 0) + row["count"]

    return {
        "filename": session.filename,
        "chars": len(text),
        "masked_count": sum(counts.values()),
        "counts": counts,
        "findings": list(findings.values()),
        "original": original,
        "masked": masked,
    }


def _expired() -> JSONResponse:
    return JSONResponse({"error": "expired"}, status_code=404)


@router.get("/api/document")
def api_document(request: Request) -> Response:
    session = current_session(request)
    return JSONResponse(document_payload(session)) if session else _expired()


@router.post("/api/tokens/{key}/toggle")
def api_toggle(request: Request, key: str) -> Response:
    """Exclude a pseudonym (every mention of that value) from masking, or mask it again."""
    if not request.app.state.limiter.allow("toggle", client_ip(request)):
        return JSONResponse({"error": "rate_limited"}, status_code=429)
    session = current_session(request)
    if session is None:
        return _expired()
    token = f"[{key}]"
    if token not in session.pseudonymizer.mapping:
        return JSONResponse({"error": "not_found"}, status_code=404)
    session.excluded ^= {token}  # add if missing, remove if present
    return JSONResponse(document_payload(session))
