"""Phase 5: HTTP request validation for POST /api/analyze-review."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from models.review import ReviewAnalysis
from services.ai_analyzer import analyzer_service

client = TestClient(app, raise_server_exceptions=False)

VALID_ANALYSIS = ReviewAnalysis(
    sentiment="positive",
    rating=4,
    rating_source="inferred",
    summary="Solid phone.",
    aspects=[],
    pros=[{"point": "Solid build", "evidence": "solid build"}],
    cons=[],
)


def _post(payload):
    return client.post("/api/analyze-review", json=payload)


def test_missing_review_field_returns_422_without_gemini_call():
    with patch.object(analyzer_service, "analyze_review") as mock_analyze:
        resp = _post({})
    assert resp.status_code == 422
    mock_analyze.assert_not_called()
    assert "detail" in resp.json()


def test_empty_review_rejected():
    with patch.object(analyzer_service, "analyze_review") as mock_analyze:
        resp = _post({"review": ""})
    assert resp.status_code == 422
    mock_analyze.assert_not_called()


def test_whitespace_only_review_rejected():
    with patch.object(analyzer_service, "analyze_review") as mock_analyze:
        resp = _post({"review": "   "})
    assert resp.status_code == 422
    mock_analyze.assert_not_called()


def test_valid_max_length_5000_accepted_by_request_schema():
    review = ("a" * 5000).strip() or "x"
    review = "x" * 4999 + "y"  # exactly 5000 non-whitespace chars
    assert len(review) == 5000
    with patch.object(analyzer_service, "analyze_review", return_value=VALID_ANALYSIS) as mock_analyze:
        resp = _post({"review": review})
    assert resp.status_code == 200
    mock_analyze.assert_called_once()
    assert resp.json()["success"] is True


def test_over_max_length_rejected():
    review = "x" * 5001
    with patch.object(analyzer_service, "analyze_review") as mock_analyze:
        resp = _post({"review": review})
    assert resp.status_code == 422
    mock_analyze.assert_not_called()


def test_valid_request_reaches_analyzer_path():
    with patch.object(analyzer_service, "analyze_review", return_value=VALID_ANALYSIS) as mock_analyze:
        resp = _post({"review": "Great product, highly recommend."})
    assert resp.status_code == 200
    mock_analyze.assert_called_once()
    mock_analyze.assert_called_with("Great product, highly recommend.")
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["sentiment"] == "positive"


def test_non_json_body_returns_422():
    resp = client.post(
        "/api/analyze-review",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
