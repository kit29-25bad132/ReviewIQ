"""Phase 5G — /intelligence endpoint and error-state tests.

Statistics always come from the real database. Only the AI stages are patched,
so these tests are deterministic and free; the fully live end-to-end proof
lives in the Phase 5I integration tests.
"""

from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from models.intelligence import (
    AnalysisErrorResponse,
    ClaimWithEvidence,
    EvidenceItem,
    ProductStatistics,
    DateRange,
)
from services.intelligence import analyzer as analyzer_module
from services.intelligence.statistics import (
    ProductStatisticsData,
    ReviewDateRange,
    aggregate_reviews_for_product,
)

client = TestClient(app)
no_raise_client = TestClient(app, raise_server_exceptions=False)

ENDPOINT = "/api/products/{pid}/intelligence"
P12 = "P12"


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    dsn = dotenv_values(env_path).get("DATABASE_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)
    from services.catalog.catalog_service import canonical_catalog

    if not canonical_catalog.is_configured():
        pytest.skip("live Supabase DSN not configured")


def _draft(summary="Grounded summary.", best_for="Best for commuters."):
    from services.intelligence.summary import SummaryDraft

    return SummaryDraft(summary=summary, best_for=best_for)


def _one_pro_claim(review_id="R00003"):
    return ClaimWithEvidence(
        claim="Solid build quality",
        evidence=[EvidenceItem(review_id=review_id, excerpt="build quality")],
        support_count=1,
    )


def _stats_with_counts(total: int) -> ProductStatisticsData:
    """Build a statistics object with a chosen review count (for state tests)."""
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    distribution[5] = total
    return ProductStatisticsData(
        product_id=str(uuid4()),
        source_product_id="P_SMALL",
        product_name="Sparse Product",
        category="Gadget",
        total_reviews=total,
        average_rating=5.0 if total else 0.0,
        rating_distribution=distribution,
        sentiment_distribution={"positive": total, "neutral": 0, "negative": 0},
        verified_purchase_count=total,
        verified_purchase_pct=100.0 if total else 0.0,
        date_range=ReviewDateRange(earliest="2025-01-01" if total else None, latest="2025-01-02" if total else None),
    )


# --------------------------------------------------------------- happy path


def test_intelligence_returns_real_statistics_and_ai_fields():
    with patch.object(analyzer_module, "extract_aspects", return_value=[]), patch.object(
        analyzer_module, "generate_pros_cons", return_value=([_one_pro_claim()], [])
    ), patch.object(analyzer_module, "generate_summary", return_value=_draft()):
        resp = client.get(ENDPOINT.format(pid=P12))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["product_id"] == P12
    assert body["product_name"].startswith("Kelto")
    assert body["data_source"] == "supabase"
    assert body["ai_unavailable"] is False
    assert body["low_review_count"] is False
    assert body["summary"] == "Grounded summary."
    assert body["best_for"] == "Best for commuters."
    assert body["review_count_used"] == body["statistics"]["total_reviews"]

    # Statistics are real and internally consistent.
    stats = body["statistics"]
    assert stats["total_reviews"] == 95
    assert sum(stats["rating_distribution"].values()) == 95
    assert sorted(stats["rating_distribution"].keys()) == ["1", "2", "3", "4", "5"]
    assert stats["date_range"] == {"earliest": "2024-10-12", "latest": "2026-09-25"}
    assert 0.0 <= stats["verified_purchase_pct"] <= 100.0

    # Pros carry traceable evidence.
    assert len(body["pros"]) == 1
    assert body["pros"][0]["evidence"][0]["review_id"] == "R00003"
    assert body["generated_at"]


def test_statistics_match_a_direct_database_query():
    with patch.object(analyzer_module, "extract_aspects", return_value=[]), patch.object(
        analyzer_module, "generate_pros_cons", return_value=([], [])
    ), patch.object(analyzer_module, "generate_summary", return_value=_draft()):
        body = client.get(ENDPOINT.format(pid=P12)).json()

    from services.catalog.catalog_service import canonical_catalog

    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*), ROUND(AVG(r.rating)::numeric, 1)
                FROM public.reviews r JOIN public.products p ON r.product_id = p.id
                WHERE p.source_product_id = 'P12';
                """
            )
            total, avg = cur.fetchone()

    assert body["statistics"]["total_reviews"] == int(total)
    assert body["statistics"]["average_rating"] == float(avg)


# ------------------------------------------------------------- error states


def test_unknown_product_returns_404_with_a_clear_message():
    resp = client.get(ENDPOINT.format(pid="NONEXISTENT_99999"))
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_product_with_zero_reviews_returns_zeros_and_insufficient_summary():
    with patch.object(
        analyzer_module, "compute_statistics", return_value=_stats_with_counts(0)
    ):
        resp = client.get(ENDPOINT.format(pid="P122"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"] == "Insufficient reviews"
    assert body["best_for"] == ""
    assert body["review_count_used"] == 0
    assert body["aspects"] == [] and body["pros"] == [] and body["cons"] == []
    assert body["statistics"]["total_reviews"] == 0
    assert body["statistics"]["average_rating"] == 0.0
    assert body["statistics"]["rating_distribution"] == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    assert body["low_review_count"] is False


def test_fewer_than_five_reviews_sets_low_review_count():
    with patch.object(
        analyzer_module, "compute_statistics", return_value=_stats_with_counts(3)
    ), patch.object(analyzer_module, "extract_aspects", return_value=[]), patch.object(
        analyzer_module, "generate_pros_cons", return_value=([], [])
    ), patch.object(analyzer_module, "generate_summary", return_value=_draft()):
        body = client.get(ENDPOINT.format(pid="P123")).json()
    assert body["low_review_count"] is True
    assert body["statistics"]["total_reviews"] == 3


def test_ai_failure_keeps_statistics_and_flags_ai_unavailable():
    with patch.object(
        analyzer_module, "extract_aspects", side_effect=RuntimeError("gemini down")
    ), patch.object(
        analyzer_module, "generate_pros_cons", side_effect=RuntimeError("gemini down")
    ), patch.object(analyzer_module, "generate_summary", return_value=None):
        resp = client.get(ENDPOINT.format(pid=P12))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_unavailable"] is True
    assert body["aspects"] == [] and body["pros"] == [] and body["cons"] == []
    assert body["best_for"] == ""
    # The statistics survive untouched.
    assert body["statistics"]["total_reviews"] == 95
    assert sum(body["statistics"]["sentiment_distribution"].values()) == 95


def test_validation_failure_returns_a_safe_statistics_only_fallback():
    invalid = AnalysisErrorResponse(code="validation_error", error="nope")
    with patch.object(analyzer_module, "extract_aspects", return_value=[]), patch.object(
        analyzer_module, "generate_pros_cons", return_value=([], [])
    ), patch.object(analyzer_module, "generate_summary", return_value=_draft()), patch.object(
        analyzer_module, "validate_analysis_response", return_value=invalid
    ):
        resp = client.get(ENDPOINT.format(pid=P12))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "statistics" in body
    assert body["statistics"]["total_reviews"] == 95
    assert body["ai_unavailable"] is True
    assert body["pros"] == [] and body["cons"] == []


def test_unrecoverable_validation_returns_a_structured_error_not_a_500():
    invalid = AnalysisErrorResponse(code="validation_error", error="nope")
    with patch.object(analyzer_module, "extract_aspects", return_value=[]), patch.object(
        analyzer_module, "generate_pros_cons", return_value=([], [])
    ), patch.object(analyzer_module, "generate_summary", return_value=_draft()), patch.object(
        analyzer_module, "validate_analysis_response", return_value=invalid
    ), patch.object(analyzer_module, "_assemble", side_effect=RuntimeError("cannot assemble")):
        resp = no_raise_client.get(ENDPOINT.format(pid=P12))

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "validation_error"
    assert "error" in body


def test_unconfigured_catalog_returns_503():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(canonical_catalog, "is_configured", return_value=False):
        resp = no_raise_client.get(ENDPOINT.format(pid=P12))
    assert resp.status_code == 503


def test_database_error_is_not_masked():
    with patch.object(
        analyzer_module, "compute_statistics", side_effect=RuntimeError("supabase down")
    ):
        resp = no_raise_client.get(ENDPOINT.format(pid=P12))
    assert resp.status_code == 500


def test_aggregate_helper_reports_zeroes_for_an_unknown_uuid():
    """Sanity check the zero-state source used above is genuinely from SQL."""
    zeros = aggregate_reviews_for_product(str(uuid4()))
    assert zeros["total_reviews"] == 0
    assert zeros["rating_distribution"] == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
