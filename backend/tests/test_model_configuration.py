"""Task 1 tests: Gemini model configuration (offline, no network calls).

Covers:
- Default primary model is the pinned stable model (gemini-3.8-flash).
- Model ordering: GEMINI_MODEL override moves the primary first, verified fallbacks follow.
- Model list is bounded (max 3 attempts) and contains no preview / 2.5-family names.
- Duplicate prevention when GEMINI_MODEL equals a fallback.
- The successful model name is logged.
- Configuration error when GEMINI_API_KEY is missing.
- Clear RuntimeError when the google-genai SDK is not installed.
- GEMINI_MODEL is documented in backend/.env.example.

Note: the legacy google-generativeai path was removed (ADR-003), so there is no
legacy ordering to test.
"""

import logging
import os
import sys
from unittest import mock

import pytest

from services.ai_analyzer import (
    DEFAULT_MODEL_NAME,
    FALLBACK_MODEL_NAMES,
    _build_model_list,
    analyzer_service,
)


def test_default_primary_is_pinned_stable_model():
    assert DEFAULT_MODEL_NAME == "gemini-3.8-flash"


def test_build_model_list_default():
    models = _build_model_list(None)
    assert models == ["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash"]


def test_build_model_list_env_override_moves_primary_first():
    # An explicit GEMINI_MODEL replaces the primary; the two verified
    # fallbacks are kept in order (see docs/19_DECISIONS.md ADR-002).
    models = _build_model_list("gemini-3.5-flash-lite")
    assert models == ["gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3.5-flash"]


def test_build_model_list_env_override_equal_to_fallback_has_no_duplicate():
    models = _build_model_list("gemini-flash-latest")
    assert models == ["gemini-flash-latest", "gemini-3.5-flash"]
    assert len(models) == len(set(models))


def test_fallback_models_are_verified_names():
    for name in FALLBACK_MODEL_NAMES:
        assert "preview" not in name
        assert not name.startswith("gemini-2.5")
    assert len(FALLBACK_MODEL_NAMES) <= 2


def test_model_list_is_bounded_to_three_attempts():
    assert len(_build_model_list(None)) <= 3
    assert len(_build_model_list("custom-model")) <= 3


class _FakeResponse:
    text = '{"sentiment": "positive", "rating": 4, "pros": [], "cons": [], "summary": "ok"}'


class _FakeModels:
    def __init__(self, attempts, fail_first=0):
        self.attempts = attempts
        self.fail_first = fail_first

    def generate_content(self, model, contents, config):
        self.attempts.append(model)
        if len(self.attempts) <= self.fail_first:
            raise RuntimeError(f"model {model} unavailable")
        return _FakeResponse()


class _FakeClient:
    def __init__(self, attempts, fail_first=0):
        self.models = _FakeModels(attempts, fail_first)


def _install_fake_sdk(monkeypatch, attempts, fail_first=0):
    """Install a fake google-genai SDK in sys.modules (no network, no real install)."""
    fake_genai = mock.MagicMock()
    fake_genai.Client = lambda api_key: _FakeClient(attempts, fail_first)
    fake_types = mock.MagicMock()
    monkeypatch.setitem(sys.modules, "google", mock.MagicMock(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)


def _run_genai_call(monkeypatch, attempts, fail_first=0):
    """Run the google-genai call path with a fake SDK client (no network, no install)."""
    _install_fake_sdk(monkeypatch, attempts, fail_first)
    return analyzer_service._call_google_genai("A great product. Works well.")


def test_successful_model_is_logged(monkeypatch, caplog):
    attempts = []
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    with caplog.at_level(logging.INFO, logger="services.ai_analyzer"):
        _run_genai_call(monkeypatch, attempts)

    assert attempts == [DEFAULT_MODEL_NAME]
    assert any(
        DEFAULT_MODEL_NAME in rec.message and "succeeded using model" in rec.message
        for rec in caplog.records
    )


def test_env_model_override_is_used_first(monkeypatch):
    attempts = []
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    _run_genai_call(monkeypatch, attempts)
    assert attempts[0] == "gemini-3.5-flash-lite"
    assert len(attempts) == 1


def test_gemini_model_documented_in_env_example():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, ".env.example"), encoding="utf-8") as fh:
        content = fh.read()
    assert "GEMINI_MODEL" in content
    assert "gemini-3.8-flash" in content


def test_max_three_attempts_when_all_models_fail(monkeypatch):
    attempts = []
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="unavailable"):
        _run_genai_call(monkeypatch, attempts, fail_first=99)

    assert attempts == [DEFAULT_MODEL_NAME, *FALLBACK_MODEL_NAMES]
    assert len(attempts) <= 3


def test_fallback_used_in_order_after_primary_failure(monkeypatch, caplog):
    attempts = []
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    with caplog.at_level(logging.INFO, logger="services.ai_analyzer"):
        _run_genai_call(monkeypatch, attempts, fail_first=1)

    # Primary fails once, first verified fallback is tried next and succeeds.
    assert attempts == [DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES[0]]
    assert any(
        FALLBACK_MODEL_NAMES[0] in rec.message and "succeeded using model" in rec.message
        for rec in caplog.records
    )


def test_missing_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.setattr("services.ai_analyzer.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        analyzer_service.analyze_review("Some customer review text.")


def test_missing_sdk_raises_clear_install_error(monkeypatch):
    # Simulate the SDK not being installed: sys.modules entry set to None makes
    # 'from google import genai' raise ImportError.
    monkeypatch.setitem(sys.modules, "google", None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    with pytest.raises(RuntimeError, match="google-genai"):
        analyzer_service.analyze_review("Some customer review text.")
