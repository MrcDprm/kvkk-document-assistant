import io

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import create_app
from app.web import SESSION_COOKIE
from tests.fake_llm import FakeLLM
from tests.test_ner import FakeNer
from tests.test_app import make_settings

SAMPLE = "Kiracı Ayşe Yılmaz (T.C. 10000000146), Tel: 0532 123 45 67. Ödeme her ayın 5'inde yapılır."


@pytest.fixture
def client():
    return TestClient(create_app(make_settings()))


def analyze_text(client, text=SAMPLE):
    return client.post("/analyze", data={"mode": "text", "text": text}, follow_redirects=False)


# --- Home ---

def test_home_renders_in_turkish_by_default(client):
    response = client.get("/")
    assert response.status_code == 200
    assert '<html lang="tr">' in response.text
    assert "Kişisel verileri bul" in response.text


def test_home_in_english_from_browser_language(client):
    response = client.get("/", headers={"accept-language": "en-US,en;q=0.9"})
    assert '<html lang="en">' in response.text


def test_language_switch_sets_cookie_and_redirects_locally(client):
    response = client.get("/lang/en?next=/document", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/document"
    assert "lang=en" in response.headers["set-cookie"]


@pytest.mark.parametrize("target", ["//evil.com", "https://evil.com", "/\\evil.com"])
def test_language_switch_blocks_open_redirect(client, target):
    response = client.get(f"/lang/tr?next={target}", follow_redirects=False)
    assert response.headers["location"] == "/"


def test_unknown_error_code_in_url_is_ignored(client):
    response = client.get("/?error=<script>alert(1)</script>")
    assert "<script>alert(1)" not in response.text
    assert 'role="alert"' not in response.text


def test_known_error_code_is_shown(client):
    assert "Oturumunuzun süresi doldu" in client.get("/?error=expired").text


# --- Analyze ---

def test_analyze_text_creates_session(client):
    response = analyze_text(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/document"
    cookie = response.headers["set-cookie"]
    assert SESSION_COOKIE in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_session_cookie_is_secure_in_production():
    client = TestClient(create_app(make_settings(cookie_secure=True)), base_url="https://testserver")
    assert "Secure" in analyze_text(client).headers["set-cookie"]


def test_analyze_docx_upload(client):
    document = Document()
    document.add_paragraph(SAMPLE)
    data = io.BytesIO()
    document.save(data)
    response = client.post(
        "/analyze",
        data={"mode": "file"},
        files={"file": ("sozlesme.docx", data.getvalue(), "application/octet-stream")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    payload = client.get("/api/document").json()
    assert payload["filename"] == "sozlesme.docx"
    assert {f["type"] for f in payload["findings"]} == {"KISI", "TCKN", "TELEFON"}


def test_analyze_demo(client):
    client.post("/analyze", data={"mode": "demo", "demo": "kira-sozlesmesi"})
    payload = client.get("/api/document").json()
    assert payload["filename"] == "demo-kira-sozlesmesi.txt"
    assert payload["masked_count"] > 5


def test_analyze_without_file_shows_error(client):
    response = client.post("/analyze", data={"mode": "file"})
    assert response.status_code == 400
    assert "Lütfen bir dosya seçin" in response.text


def test_analyze_bad_file_shows_error(client):
    response = client.post(
        "/analyze", data={"mode": "file"}, files={"file": ("virus.exe", b"MZ...", "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "desteklenmiyor" in response.text


def test_empty_paste_keeps_form_on_text_tab(client):
    response = client.post("/analyze", data={"mode": "text", "text": "   "})
    assert response.status_code == 400
    assert 'id="mode-text" value="text" checked' in response.text


def test_pasted_text_is_escaped_when_shown_again():
    client = TestClient(create_app(make_settings(max_text_chars=10)))
    response = client.post("/analyze", data={"mode": "text", "text": "</textarea><script>x</script>"})
    assert "<script>x</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_oversized_body_is_rejected_before_parsing():
    client = TestClient(create_app(make_settings(max_upload_bytes=1000)))
    response = client.post(
        "/analyze",
        data={"mode": "file"},
        files={"file": ("big.txt", b"a" * (400 * 1024), "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/?error=too_large"


def test_new_upload_replaces_previous_session(client):
    analyze_text(client)
    first = client.cookies.get(SESSION_COOKIE)
    analyze_text(client, "Mehmet Kaya aradı.")
    store = client.app.state.store
    assert store.get(first) is None
    assert len(store) == 1


def test_rate_limit_on_analyze(client):
    client.app.state.limiter._limits["analyze"] = (2, 60)
    analyze_text(client)
    analyze_text(client)
    assert analyze_text(client).status_code == 429


def test_cross_site_post_is_refused(client):
    response = client.post("/analyze", data={"mode": "text", "text": SAMPLE}, headers={"origin": "https://evil.com"})
    assert response.status_code == 403


def test_same_site_post_with_origin_is_allowed(client):
    response = client.post(
        "/analyze", data={"mode": "text", "text": SAMPLE}, headers={"origin": "http://testserver"}, follow_redirects=False
    )
    assert response.status_code == 303


# --- Document view ---

def test_document_page_requires_session(client):
    response = client.get("/document", follow_redirects=False)
    assert response.headers["location"] == "/"


def test_document_page_with_expired_cookie(client):
    client.cookies.set(SESSION_COOKIE, "does-not-exist")
    response = client.get("/document", follow_redirects=False)
    assert response.headers["location"] == "/?error=expired"


def test_document_page_has_i18n_data_block(client):
    analyze_text(client)
    response = client.get("/document")
    assert response.status_code == 200
    assert '<script type="application/json" id="i18n">' in response.text


def test_api_document_segments(client):
    analyze_text(client)
    data = client.get("/api/document").json()
    assert "".join(s["text"] for s in data["original"]) == SAMPLE
    masked = "".join(s["text"] for s in data["masked"])
    assert masked == "Kiracı [KISI_1] (T.C. [TCKN_1]), Tel: [TELEFON_1]. Ödeme her ayın 5'inde yapılır."
    assert data["counts"] == {"KISI": 1, "TCKN": 1, "TELEFON": 1}


def test_api_document_without_session(client):
    response = client.get("/api/document")
    assert response.status_code == 404
    assert response.json() == {"error": "expired"}


def test_toggle_excludes_and_includes_again(client):
    analyze_text(client)
    data = client.post("/api/tokens/KISI_1/toggle").json()
    assert data["findings"][0]["excluded"] is True
    assert "Ayşe Yılmaz" in "".join(s["text"] for s in data["masked"])
    assert data["masked_count"] == 2

    data = client.post("/api/tokens/KISI_1/toggle").json()
    assert data["findings"][0]["excluded"] is False
    assert data["findings"][0]["token"] == "[KISI_1]"  # same token as before


def test_findings_are_grouped_by_pseudonym(client):
    analyze_text(client, "Ayşe Yılmaz aradı. AYŞE YILMAZ tekrar aradı. Mehmet Kaya da aradı.")
    data = client.get("/api/document").json()
    assert [(f["token"], f["text"], f["count"]) for f in data["findings"]] == [
        ("[KISI_1]", "Ayşe Yılmaz", 2),
        ("[KISI_2]", "Mehmet Kaya", 1),
    ]


def test_excluding_a_pseudonym_unmasks_every_mention(client):
    analyze_text(client, "Ayşe Yılmaz aradı. AYŞE YILMAZ tekrar aradı.")
    data = client.post("/api/tokens/KISI_1/toggle").json()
    assert "".join(s["text"] for s in data["masked"]) == "Ayşe Yılmaz aradı. AYŞE YILMAZ tekrar aradı."
    assert data["masked_count"] == 0


@pytest.mark.parametrize("key", ["KISI_99", "kisi_1", "x", "%5BKISI_1%5D"])
def test_toggle_unknown_token(client, key):
    analyze_text(client)
    assert client.post(f"/api/tokens/{key}/toggle").status_code == 404


def test_reset_deletes_session(client):
    analyze_text(client)
    session_id = client.cookies.get(SESSION_COOKIE)
    response = client.post("/reset", follow_redirects=False)
    assert response.headers["location"] == "/"
    assert client.app.state.store.get(session_id) is None


def test_404_page(client):
    response = client.get("/olmayan-sayfa")
    assert response.status_code == 404
    assert "Sayfa bulunamadı" in response.text


def test_static_files_are_served(client):
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/favicon.svg").status_code == 200


def test_null_origin_is_refused(client):
    # Sent by sandboxed iframes on other sites; our own pages send their real origin.
    response = client.post("/analyze", data={"mode": "text", "text": SAMPLE}, headers={"origin": "null"})
    assert response.status_code == 403


def test_referrer_policy_keeps_origin_for_own_posts(client):
    assert client.get("/").headers["referrer-policy"] == "same-origin"


# --- Questions and audit log ---


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def ask_client(llm):
    return TestClient(create_app(make_settings(), llm=llm))


def test_ask_answers_with_real_values(ask_client, llm):
    analyze_text(ask_client)
    response = ask_client.post("/api/ask", json={"question": "Kiracı kim?"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Ayşe Yılmaz kiracıdır [1]."
    assert "Ayşe" not in llm.sent_texts()


def test_audit_shows_what_was_sent(ask_client):
    analyze_text(ask_client)
    assert ask_client.get("/api/audit").json() == {"entries": []}
    ask_client.post("/api/ask", json={"question": "Ayşe Yılmaz kim?"})
    [entry] = ask_client.get("/api/audit").json()["entries"]
    assert entry["kind"] == "answer"
    assert "[KISI_1] kim?" in entry["sent_text"]
    assert "Ayşe" not in entry["sent_text"]
    assert entry["input_tokens"] == 120


@pytest.mark.parametrize("body", [{}, {"question": 42}, {"question": None}, [], "text"])
def test_ask_rejects_bad_bodies(ask_client, body):
    analyze_text(ask_client)
    assert ask_client.post("/api/ask", json=body).status_code == 400


def test_ask_rejects_invalid_json(ask_client):
    analyze_text(ask_client)
    response = ask_client.post("/api/ask", content=b"{not json", headers={"content-type": "application/json"})
    assert response.status_code == 400


def test_ask_without_session(ask_client):
    assert ask_client.post("/api/ask", json={"question": "x"}).status_code == 404


@pytest.mark.parametrize("code, status", [("quota", 429), ("unavailable", 503), ("blocked", 502)])
def test_llm_errors_become_codes(code, status):
    client = TestClient(create_app(make_settings(), llm=FakeLLM(error=code)))
    analyze_text(client)
    response = client.post("/api/ask", json={"question": "Kira?"})
    assert response.status_code == status
    assert response.json() == {"error": code}


def test_ask_disabled_without_key(client):
    analyze_text(client)
    assert client.post("/api/ask", json={"question": "x"}).json() == {"error": "disabled"}
    assert "Soru sorma bu sunucuda kapalı" in client.get("/document").text


def test_ask_rate_limit(ask_client):
    ask_client.app.state.limiter._limits["ask"] = (1, 60)
    analyze_text(ask_client)
    ask_client.post("/api/ask", json={"question": "a?"})
    assert ask_client.post("/api/ask", json={"question": "b?"}).json() == {"error": "rate_limited"}


# --- Trained name model ---


def test_analysis_uses_the_model_and_says_so():
    client = TestClient(create_app(make_settings(), ner=FakeNer(PER=["Tayyar Gündoğdu"])))
    analyze_text(client, "Tayyar Gündoğdu imzaladı.")
    data = client.get("/api/document").json()
    assert data["detector"] == "model"
    assert [f["text"] for f in data["findings"]] == ["Tayyar Gündoğdu"]


def test_rules_only_without_model(client):
    analyze_text(client)
    assert client.get("/api/document").json()["detector"] == "rules"
    assert client.app.state.ner is None


def test_question_is_masked_with_the_model_too():
    llm = FakeLLM()
    # "Cebrail Tuzcuoğlu" is not in the document; only the model can find it in the question.
    client = TestClient(create_app(make_settings(), llm=llm, ner=FakeNer(PER=["Cebrail Tuzcuoğlu"])))
    analyze_text(client)
    client.post("/api/ask", json={"question": "Cebrail Tuzcuoğlu kim?"})
    assert "Cebrail" not in llm.sent_texts()
