import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings(**overrides) -> Settings:
    values = dict(
        gemini_api_key="",
        session_ttl_seconds=60,
        max_sessions=10,
        max_upload_bytes=2 * 1024 * 1024,
        cookie_secure=False,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def client():
    return TestClient(create_app(make_settings()))


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_security_headers(client):
    headers = client.get("/healthz").headers
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in headers


def test_api_docs_are_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_unexpected_error_hides_details():
    app = create_app(make_settings())

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret detail")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json() == {"error": "internal_error"}
    assert "secret detail" not in response.text
    assert "content-security-policy" in response.headers
