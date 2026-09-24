"""Phase 5: GET /health endpoint contract."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app, raise_server_exceptions=False)


def test_health_returns_200_with_expected_fields():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "Product Review Analyzer Backend"
    assert body["ai_provider"] == "Google Gemini"
    assert isinstance(body["ai_configured"], bool)
    assert "version" in body


def test_health_does_not_leak_secrets():
    resp = client.get("/health")
    assert resp.status_code == 200
    text = resp.text.lower()
    assert "ai_za" not in text
    assert "api_key=" not in text
    assert "service_role" not in text
    assert "secret" not in text
