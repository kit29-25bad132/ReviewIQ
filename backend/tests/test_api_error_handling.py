"""Phase 4.5: API error responses must not leak provider/parser internals."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from models.review import ReviewAnalysis, AnalyzeReviewResponse
from services.ai_analyzer import analyzer_service

client = TestClient(app, raise_server_exceptions=False)

VALID_ANALYSIS = ReviewAnalysis(
    sentiment="positive",
    rating=4,
    rating_source="inferred",
    summary="Great camera and display.",
    aspects=[],
    pros=[{"point": "Great camera", "evidence": "camera is excellent"}],
    cons=[],
)


def _post(review: str = "The camera is excellent."):
    return client.post("/api/analyze-review", json={"review": review})


def test_success_response_contract_unchanged():
    with patch.object(analyzer_service, "analyze_review", return_value=VALID_ANALYSIS):
        resp = _post()
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None
    data = body["data"]
    assert data["sentiment"] == "positive"
    assert data["rating"] == 4
    assert data["rating_source"] == "inferred"
    assert data["pros"] == [{"point": "Great camera", "evidence": "camera is excellent"}]
    envelope = AnalyzeReviewResponse.model_validate(body)
    assert envelope.success is True


def test_unknown_provider_exception_does_not_leak_raw_text():
    secret = "RAW_PROVIDER_INTERNAL_stack=Frame AIzaSECRET"
    with patch.object(
        analyzer_service, "analyze_review", side_effect=RuntimeError(secret)
    ):
        resp = _post()
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert secret not in resp.text
    assert "RAW_PROVIDER_INTERNAL" not in detail
    assert detail == "AI analysis failed. Please try again."


def test_value_error_with_model_output_does_not_leak():
    raw_output = '{"malformed": true, "token": "sk-fake-model-output"}'
    message = f"Failed to parse AI output as JSON:Expecting value. Raw output: {raw_output}"
    with patch.object(analyzer_service, "analyze_review", side_effect=ValueError(message)):
        resp = _post()
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert raw_output not in resp.text
    assert "sk-fake-model-output" not in detail
    assert detail == "Review analysis failed validation. Please try again."


def test_pydantic_validation_error_does_not_leak_input():
    # Pydantic ValidationError subclasses ValueError and may embed model input.
    with patch.object(
        analyzer_service,
        "analyze_review",
        side_effect=ValueError("1 validation error for ReviewAnalysis\n rating\n  Input should be less than or equal to 7"),
    ):
        resp = _post()
    assert resp.status_code == 400
    assert "validation error for ReviewAnalysis" not in resp.text


def test_missing_api_key_value_error_keeps_useful_config_message():
    with patch.object(
        analyzer_service,
        "analyze_review",
        side_effect=ValueError(
            "Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env"
        ),
    ):
        resp = _post()
    assert resp.status_code == 400
    assert "GEMINI_API_KEY" in resp.json()["detail"]


def test_rate_limit_categorization_preserved():
    with patch.object(
        analyzer_service,
        "analyze_review",
        side_effect=Exception("429 Quota exceeded for quota metric 'generateContent'"),
    ):
        resp = _post()
    assert resp.status_code == 500
    assert resp.json()["detail"] == "API rate limit reached. Please try again in a few moments."


def test_auth_error_categorization_preserved_without_key_material():
    with patch.object(
        analyzer_service,
        "analyze_review",
        side_effect=Exception("401 UNAUTHENTICATED api_key=AIzaSyActualKeyWouldNotAppear"),
    ):
        resp = _post()
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert detail == "Invalid or unauthenticated Gemini API key. Please check backend/.env"
    assert "AIzaSyActualKeyWouldNotAppear" not in resp.text


def test_timeout_categorization_preserved():
    with patch.object(
        analyzer_service,
        "analyze_review",
        side_effect=TimeoutError("Connection to genai.googleapis.com timed out"),
    ):
        resp = _post()
    assert resp.status_code == 500
    assert (
        resp.json()["detail"]
        == "Connection to AI service timed out or unavailable. Please verify your network connection."
    )


def test_fallback_exhaustion_http_is_safe_generic_500():
    # Graph re-raises the last provider error after all 5 models fail.
    secret = "generateContent failed model=gemini-3.5-flash-lite internals=/var/log/aizaSECRET"
    with patch.object(analyzer_service, "analyze_review", side_effect=RuntimeError(secret)):
        resp = _post()
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert secret not in resp.text
    assert "aizaSECRET" not in detail
    assert detail == "AI analysis failed. Please try again."


def test_fallback_exhaustion_parse_failure_http_is_safe_400():
    # All models returned unparseable output; last_error is a ValueError with raw text.
    with patch.object(
        analyzer_service,
        "analyze_review",
        side_effect=ValueError(
            'Failed to parse AI output as JSON:Expecting value. Raw output: {"oops": true, "token": "sk-leak"}'
        ),
    ):
        resp = _post()
    assert resp.status_code == 400
    assert "sk-leak" not in resp.text
    assert resp.json()["detail"] == "Review analysis failed validation. Please try again."


def test_grounding_filters_fabricated_evidence_via_http(monkeypatch):
    """Successful HTTP analysis path runs grounding before the response is returned."""
    import json

    from services.grounding_service import is_evidence_supported
    from tests.test_model_configuration import _FakeResponse, _install_fake_sdk

    review = "The battery lasts all day and the display is bright."
    payload = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "Praises battery and display.",
        "aspects": [],
        "pros": [
            {"point": "All-day battery", "evidence": "The battery lasts all day"},
            {"point": "Waterproof body", "evidence": "completely waterproof military grade"},
        ],
        "cons": [],
    }
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(_FakeResponse, "text", json.dumps(payload))
    attempts: list = []
    _install_fake_sdk(monkeypatch, attempts)

    resp = _post(review)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    points = [p["point"] for p in body["data"]["pros"]]
    assert "All-day battery" in points
    assert "Waterproof body" not in points
    for pro in body["data"]["pros"]:
        assert is_evidence_supported(review, pro["evidence"])
    assert attempts


def test_global_exception_handler_returns_safe_envelope():
    """Unhandled exception outside route try/except hits main.global_exception_handler."""
    secret = "INTERNAL_db_password=Hunter2xyz stack=Frame"
    with patch.object(
        analyzer_service,
        "is_configured",
        side_effect=RuntimeError(secret),
    ):
        resp = client.get("/health")

    assert resp.status_code == 500
    body = resp.json()
    assert body == {
        "success": False,
        "data": None,
        "error": "An unexpected internal server error occurred.",
    }
    assert secret not in resp.text
    assert "Traceback" not in resp.text
    assert "Hunter2" not in resp.text
    assert "stack=" not in resp.text


def _install_scripted_empty_then_valid_sdk(monkeypatch, attempts, script):
    """Fake SDK: each generate_content call pops the next script entry (str or '')."""
    import sys
    from unittest import mock

    class _Resp:
        def __init__(self, text: str):
            self.text = text

    class _ScriptedModels:
        def __init__(self):
            self._script = list(script)

        def generate_content(self, model, contents, config):
            attempts.append(model)
            idx = len(attempts) - 1
            step = self._script[idx] if idx < len(self._script) else self._script[-1]
            return _Resp(step)

    class _ScriptedClient:
        models = _ScriptedModels()

    fake_genai = mock.MagicMock()
    fake_genai.Client = lambda api_key: _ScriptedClient()
    fake_types = mock.MagicMock()
    monkeypatch.setitem(sys.modules, "google", mock.MagicMock(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)


def test_empty_gemini_response_all_models_safe_http_error(monkeypatch):
    """All models return empty text → no success payload, safe 500, no raw internals."""
    import json

    from services.ai_analyzer import DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES
    from tests.test_model_configuration import _FakeResponse, _install_fake_sdk

    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(_FakeResponse, "text", "")
    attempts: list = []
    _install_fake_sdk(monkeypatch, attempts)

    resp = _post("The battery lasts all day.")
    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "AI analysis failed. Please try again."
    # Empty output counts as a failed attempt for every configured model.
    assert attempts == [DEFAULT_MODEL_NAME, *FALLBACK_MODEL_NAMES]
    assert "success" not in body or body.get("success") is not True
    assert "Empty response" not in resp.text
    assert "stack" not in resp.text.lower()
    # Never a false success envelope with analysis data
    assert "sentiment" not in body


def test_empty_then_valid_gemini_response_falls_back_via_http(monkeypatch):
    """First model empty → fallback model succeeds; HTTP returns 200 analysis."""
    import json

    from services.ai_analyzer import DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES

    valid = json.dumps(
        {
            "sentiment": "positive",
            "rating": 5,
            "rating_source": "inferred",
            "summary": "Strong battery life.",
            "aspects": [
                {
                    "aspect": "battery",
                    "sentiment": "positive",
                    "evidence": "The battery lasts all day",
                }
            ],
            "pros": [
                {"point": "All-day battery", "evidence": "The battery lasts all day"}
            ],
            "cons": [],
        }
    )
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-secret")
    attempts: list = []
    _install_scripted_empty_then_valid_sdk(monkeypatch, attempts, ["", valid])

    resp = _post("The battery lasts all day.")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["sentiment"] == "positive"
    assert body["data"]["rating"] == 5
    assert attempts == [DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES[0]]
