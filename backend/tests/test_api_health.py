"""Phase 5: GET /health endpoint contract.

Gate 2 (Phase 4): /health must not advertise a hardcoded provider identity or
a version that drifts from the app's version source. Provider reporting is
derived from which API keys are actually configured; keys themselves are
never exposed.
"""

from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app, raise_server_exceptions=False)

_ALL_PROVIDER_KEYS = ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY")


def _clear_provider_keys(monkeypatch):
    for key in _ALL_PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_health_returns_200_with_expected_fields(monkeypatch):
    _clear_provider_keys(monkeypatch)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "Product Review Analyzer Backend"
    assert isinstance(body["ai_configured"], bool)
    assert "version" in body


def test_health_version_matches_app_version_source(monkeypatch):
    _clear_provider_keys(monkeypatch)
    resp = client.get("/health")
    body = resp.json()
    assert body["version"] == main.APP_VERSION
    assert body["version"] == app.version


def test_health_reports_no_provider_when_none_configured(monkeypatch):
    _clear_provider_keys(monkeypatch)
    resp = client.get("/health")
    assert resp.status_code == 200
    # Truthful: nothing configured -> no provider claim at all.
    assert resp.json()["ai_provider"] == ""


def test_health_reports_only_actually_configured_providers(monkeypatch):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-a-real-secret")
    resp = client.get("/health")
    body = resp.json()
    # Derived from actual configuration; unconfigured providers are absent.
    assert body["ai_provider"] == "gemini, groq"
    assert body["ai_configured"] is True
    # Keys themselves are never exposed.
    text = resp.text.lower()
    assert "test-key-not-a-real-secret" not in text


def test_health_missing_optional_provider_keys_do_not_change_service_health(monkeypatch):
    """No keys configured: the service itself is still healthy; only the
    ai_configured flag and provider list reflect the missing configuration."""
    _clear_provider_keys(monkeypatch)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["ai_configured"] is False


def test_health_does_not_leak_secrets(monkeypatch):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "ai_za-canary-secret-value")
    resp = client.get("/health")
    assert resp.status_code == 200
    text = resp.text.lower()
    assert "ai_za" not in text
    assert "api_key=" not in text
    assert "service_role" not in text
    assert "secret" not in text
