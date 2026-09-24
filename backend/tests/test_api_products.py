"""Phase 5: Product / retrieval API coverage (mocked services, offline)."""

from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient

from main import app
from models.ecommerce import (
    AISummaryResponse,
    PersonalizedRecommendationResponse,
    ProductAnalysisResponse,
    ProductSearchResponse,
    ProductStatistics,
    ProductSummary,
    ProsConsAnalysisResponse,
    ReviewItem,
    ReviewsPaginationResponse,
    UserRequirementRequest,
)
from services.ecommerce_db_service import ecommerce_db_service
from services.gemini_summary_service import gemini_summary_service
from services.pros_cons_service import pros_cons_service
from services.recommendation_service import recommendation_service

client = TestClient(app, raise_server_exceptions=False)

PRODUCT = ProductSummary(
    product_id="9640962",
    product_title="Electric Toothbrush",
    category="Health & Personal Care",
    review_count=100,
    average_rating=4.2,
)

ANALYSIS = ProductAnalysisResponse(
    product=PRODUCT,
    statistics=ProductStatistics(
        review_count=100,
        average_rating=4.2,
        rating_distribution={"1": 0, "2": 0, "3": 10, "4": 40, "5": 50},
        sentiment_distribution={"positive": 80, "neutral": 15, "negative": 5},
    ),
    recent_reviews=[],
)

PROS_CONS = ProsConsAnalysisResponse(
    product_id="9640962",
    product_title="Electric Toothbrush",
    total_analyzed_reviews=100,
    pros=[],
    cons=[],
    summary="Mostly positive.",
    top_pros=["cleans well"],
    top_cons=["battery"],
    review_volume=100,
    average_rating=4.2,
    sentiment_percentages={"positive": 80.0},
)

REVIEW_PAGE = ReviewsPaginationResponse(
    items=[],
    total=0,
    page=1,
    limit=20,
    total_pages=0,
)

AI_SUMMARY = AISummaryResponse(summary="Customers like the clean.", common_pros=["cleans well"])


def test_search_products_success():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "search_products", return_value=[PRODUCT]
    ):
        resp = client.get("/api/products/search", params={"q": "toothbrush"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["products"][0]["product_id"] == "9640962"


def test_search_products_not_found():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "search_products", return_value=[]
    ):
        resp = client.get("/api/products/search", params={"q": "zzz-no-match"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["products"] == []


def test_search_products_not_ready_returns_503():
    with patch.object(ecommerce_db_service, "is_ready", return_value=False):
        resp = client.get("/api/products/search")
    assert resp.status_code == 503
    assert "detail" in resp.json()


def test_search_invalid_limit_returns_422():
    resp = client.get("/api/products/search?limit=0")
    assert resp.status_code == 422


def test_product_analysis_success():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "get_product_analysis", return_value=ANALYSIS
    ):
        resp = client.get("/api/products/9640962/analysis")
    assert resp.status_code == 200
    assert resp.json()["product"]["product_id"] == "9640962"


def test_product_analysis_not_found_404():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "get_product_analysis", return_value=None
    ):
        resp = client.get("/api/products/does-not-exist/analysis")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_product_analysis_not_ready_503():
    with patch.object(ecommerce_db_service, "is_ready", return_value=False):
        resp = client.get("/api/products/9640962/analysis")
    assert resp.status_code == 503


def test_pros_cons_success():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        pros_cons_service, "analyze_product_pros_cons", return_value=PROS_CONS
    ):
        resp = client.get("/api/products/9640962/pros-cons")
    assert resp.status_code == 200
    assert resp.json()["product_id"] == "9640962"


def test_pros_cons_not_found_404():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        pros_cons_service, "analyze_product_pros_cons", return_value=None
    ):
        resp = client.get("/api/products/nope/pros-cons")
    assert resp.status_code == 404


def test_theme_reviews_success():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        pros_cons_service, "get_theme_reviews", return_value=[]
    ) as mock_get:
        resp = client.get(
            "/api/products/9640962/theme-reviews",
            params={"theme": "battery", "limit": 10},
        )
    assert resp.status_code == 200
    assert resp.json() == []
    mock_get.assert_called_once()


def test_theme_reviews_missing_theme_422():
    resp = client.get("/api/products/9640962/theme-reviews")
    assert resp.status_code == 422


def test_theme_reviews_invalid_limit_422():
    resp = client.get(
        "/api/products/9640962/theme-reviews", params={"theme": "battery", "limit": 0}
    )
    assert resp.status_code == 422


def test_similar_products_success():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        recommendation_service, "get_similar_products", return_value=[PRODUCT]
    ):
        resp = client.get("/api/products/9640962/similar")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_recommendation_success():
    rec = PersonalizedRecommendationResponse(
        selected_product=PRODUCT,
        recommended_product=PRODUCT,
        suitability_verdict="suitable",
        recommendation_headline="Great pick",
    )
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        recommendation_service, "generate_recommendation", return_value=rec
    ):
        resp = client.post(
            "/api/products/9640962/recommendation",
            json={"priorities": ["battery life"]},
        )
    assert resp.status_code == 200
    assert resp.json()["suitability_verdict"] == "suitable"


def test_recommendation_not_found_404():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        recommendation_service, "generate_recommendation", return_value=None
    ):
        resp = client.post("/api/products/nope/recommendation", json={})
    assert resp.status_code == 404


def test_recommendation_invalid_body_422():
    resp = client.post(
        "/api/products/9640962/recommendation",
        json={"priorities": "not-a-list"},
    )
    assert resp.status_code == 422


def test_ai_summary_success():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "get_product_analysis", return_value=ANALYSIS
    ), patch.object(
        ecommerce_db_service, "get_sample_reviews", return_value=["Great brush"]
    ), patch.object(
        gemini_summary_service, "summarize_product_reviews", return_value=AI_SUMMARY
    ):
        resp = client.post("/api/products/9640962/ai-summary")
    assert resp.status_code == 200
    assert resp.json()["summary"] == "Customers like the clean."


def test_ai_summary_not_found_404():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "get_product_analysis", return_value=None
    ):
        resp = client.post("/api/products/nope/ai-summary")
    assert resp.status_code == 404


def test_product_reviews_success():
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "get_product_reviews", return_value=REVIEW_PAGE
    ):
        resp = client.get("/api/products/9640962/reviews")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["total"] == 0


def test_product_reviews_invalid_page_422():
    resp = client.get("/api/products/9640962/reviews?page=0")
    assert resp.status_code == 422


def test_product_reviews_invalid_rating_filter_422():
    resp = client.get("/api/products/9640962/reviews?rating=9")
    assert resp.status_code == 422


def test_product_reviews_not_ready_503():
    with patch.object(ecommerce_db_service, "is_ready", return_value=False):
        resp = client.get("/api/products/9640962/reviews")
    assert resp.status_code == 503
    assert "detail" in resp.json()


def test_product_analysis_unexpected_exception_returns_safe_500():
    """Unexpected product-service failure reaches the global handler safely."""
    secret = "PostgresError: password authentication failed for user=reviewiq_db SECRET=sk-live-abc123"
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service,
        "get_product_analysis",
        side_effect=RuntimeError(secret),
    ):
        resp = client.get("/api/products/9640962/analysis")

    assert resp.status_code == 500
    body = resp.json()
    assert body == {
        "success": False,
        "data": None,
        "error": "An unexpected internal server error occurred.",
    }
    assert secret not in resp.text
    assert "sk-live-abc123" not in resp.text
    assert "PostgresError" not in resp.text
    assert "Traceback" not in resp.text


def test_ai_summary_uses_canonical_verified_model_pool(monkeypatch):
    """AI summary attempts models via _build_model_list (analyzer-verified pool)."""
    import sys
    from unittest import mock

    from services.ai_analyzer import _build_model_list

    attempted: list = []

    class _Resp:
        text = ""

    class _Models:
        def generate_content(self, model, contents, config):
            attempted.append(model)
            return _Resp()

    class _Client:
        models = _Models()

    fake_genai = mock.MagicMock()
    fake_genai.Client = lambda api_key: _Client()
    fake_types = mock.MagicMock()
    monkeypatch.setitem(sys.modules, "google", mock.MagicMock(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    with pytest.raises(RuntimeError):
        gemini_summary_service._generate_summary("prompt")

    assert attempted == _build_model_list(None)
    assert attempted[0] == "gemini-3.8-flash"
    assert "gemini-3-flash-preview" not in attempted
    assert "gemini-2.5-flash" not in attempted
    assert len(attempted) <= 5
