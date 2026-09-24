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
