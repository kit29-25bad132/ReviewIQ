"""Phase 3 Task 2: canonical product analysis cutover (live Supabase).

Verifies GET /api/products/{id}/analysis is served by CanonicalCatalogService:
- P12 returns canonical Kelto Gamer Laptop facts (95 reviews, Laptop)
- statistics and recent reviews come from canonical records
- AI summary inputs originate from canonical review samples
- unknown IDs keep the 404 contract; DB errors are never masked by SQLite
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from services import ecommerce_db_service as sqlite_module
from services.gemini_summary_service import gemini_summary_service

client = TestClient(app)
no_raise_client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


@pytest.fixture(autouse=True)
def clean_cache():
    gemini_summary_service.product_cache.invalidate()
    yield
    gemini_summary_service.product_cache.invalidate()


def _no_sqlite():
    return patch.object(
        sqlite_module.ecommerce_db_service,
        "get_product_analysis",
        side_effect=AssertionError("legacy SQLite fallback used on analysis path"),
    )


def test_p12_returns_canonical_product_facts():
    from services.gemini_summary_service import AIStructuredProductAnalysis

    mock_ai = AIStructuredProductAnalysis(
        product_id="P12",
        product_title="Kelto Gamer 16",
        summary="Synthesized from canonical reviews.",
        pros=["Performance"],
        cons=["Weight"],
        insights=["Gamers approve"],
        evidence=["Runs cool under load"],
    )
    with _no_sqlite(), patch.object(
        gemini_summary_service,
        "_generate_product_structured_analysis",
        return_value=mock_ai,
    ):
        resp = client.get("/api/products/P12/analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "P12"
    assert "Kelto Gamer" in data["product_title"]
    assert data["category"] == "Laptop"
    assert data["total_reviews"] == 95
    assert data["average_rating"] > 0
    assert sum(data["rating_distribution"].values()) == 95
    assert sum(data["sentiment"].values()) == 95
    assert len(data["recent_reviews"]) > 0
    for rev in data["recent_reviews"]:
        assert rev["product_id"] == "P12"
        assert rev["review_text"]
    assert resp.headers.get("X-Cache-Status") == "MISS"


def test_ai_summary_inputs_are_canonical_records():
    captured = {}

    def fake_generate(*args, **kwargs):
        captured.update(kwargs)
        from services.gemini_summary_service import AIStructuredProductAnalysis
        return AIStructuredProductAnalysis(
            product_id=kwargs["product_id"],
            product_title=kwargs["product_title"],
            summary="Grounded in canonical samples.",
            pros=["P"],
            cons=[],
            insights=["I"],
            evidence=[kwargs["sample_reviews"][0].split("] ", 1)[1][:60]],
        )

    with _no_sqlite(), patch.object(
        gemini_summary_service, "generate_product_analysis", side_effect=fake_generate
    ):
        resp = client.get("/api/products/P12/analysis")
    assert resp.status_code == 200
    assert captured["product_id"] == "P12"
    assert "Kelto Gamer" in captured["product_title"]
    assert captured["category"] == "Laptop"
    assert len(captured["sample_reviews"]) > 0
    assert all("R0" in s and "★" in s for s in captured["sample_reviews"])
    # Every sample carries verbatim canonical review text for grounding.
    from services.catalog.catalog_service import canonical_catalog
    canonical_texts = {
        r["review_text"]
        for r in canonical_catalog.get_reviews("P12", page=1, page_size=40)[0]
    }
    for sample in captured["sample_reviews"]:
        assert any(t in sample for t in canonical_texts)


def test_unknown_product_returns_404_without_fallback():
    with _no_sqlite():
        resp = client.get("/api/products/NONEXISTENT_99999/analysis")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_canonical_failure_is_not_masked_by_sqlite():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(
        canonical_catalog, "get_product_statistics", side_effect=RuntimeError("supabase down")
    ), _no_sqlite():
        resp = no_raise_client.get("/api/products/P12/analysis")
    assert resp.status_code == 500


def test_ai_provider_failure_keeps_canonical_facts():
    from services.ai.errors import AIErrorType, AIProviderError

    def boom(*args, **kwargs):
        raise AIProviderError("gemini timed out", AIErrorType.TIMEOUT)

    with _no_sqlite(), patch.object(
        gemini_summary_service, "generate_product_analysis", side_effect=boom
    ):
        resp = client.get("/api/products/P12/analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_available"] is False
    assert data["product_id"] == "P12"
    assert data["total_reviews"] == 95
