"""Automated Tests for ReviewIQ - Canonical Dataset Verification and RAG Grounding.

Tests:
1. Product A Isolation: Querying P01 returns ONLY P01 reviews, metrics, and sentiment (canonical Supabase).
2. Product B Distinction: Querying P05 produces distinct metrics, category, brand, and reviews (canonical Supabase).
3. Keyword Search on Canonical Data: Search queries retrieve matching products from P01-P20.
4. Superseded by test_real_product_analysis.py::test_mandatory_test_c (retired, skipped).
5. Superseded by test_mandatory_test_d canonical 404 path (retired, skipped).
6. Superseded by test_canonical_product_analysis.py AI-input test (retired, skipped).
7. Canonical Search Returns No Legacy Items: search API never serves legacy mock IDs.
8. Dataset Consistency: CSV (1,500 rows) == Supabase canonical tables (20 products, P01-P20).
"""

import csv
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from services.ecommerce_db_service import DATA_DIR
from services.gemini_summary_service import AIStructuredProductAnalysis, gemini_summary_service
from services.retrieval.database import PostgresDatabase

client = TestClient(app, raise_server_exceptions=False)
CSV_PATH = DATA_DIR / "product_reviews_dataset.csv"


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)

MOCK_AI_PRODUCT_ANALYSIS = AIStructuredProductAnalysis(
    product_id="P01",
    product_title="Zyra Nova 5G",
    summary="High performance smartphone with positive overall reception.",
    pros=["Fast performance", "Good display"],
    cons=["Battery life could be better"],
    insights=["Ideal for power users on 5G."],
    evidence=["Great phone for the price."],
)


# ==============================================================================
# TEST 1: Product A Isolation (P01)
# ==============================================================================
def test_product_a_isolation():
    """Verify that querying P01 retrieves only P01 reviews, correct category, and accurate counts."""
    with patch.object(gemini_summary_service, "generate_product_analysis", return_value=MOCK_AI_PRODUCT_ANALYSIS):
        resp = client.get("/api/products/P01/analysis")
        assert resp.status_code == 200, f"Failed to get P01 analysis: {resp.text}"
        data = resp.json()

        assert data["product_id"] == "P01"
        assert "Zyra Nova 5G" in data["product_title"]
        assert data["category"] == "Smartphone"
        assert data["total_reviews"] == 74
        assert round(data["average_rating"], 2) == 3.08

        # Check reviews endpoint for P01
        rev_resp = client.get("/api/products/P01/reviews?limit=100")
        assert rev_resp.status_code == 200
        rev_data = rev_resp.json()
        assert rev_data["total"] == 74
        assert len(rev_data["items"]) == 74
        for r in rev_data["items"]:
            assert r["product_id"] == "P01"


# ==============================================================================
# TEST 2: Product B Distinction (P05)
# ==============================================================================
def test_product_b_distinction():
    """Verify that querying P05 produces completely distinct metrics, category, brand, and reviews from P01."""
    with patch.object(gemini_summary_service, "generate_product_analysis", return_value=MOCK_AI_PRODUCT_ANALYSIS):
        resp_a = client.get("/api/products/P01/analysis").json()
        resp_b = client.get("/api/products/P05/analysis").json()

        assert resp_b["product_id"] == "P05"
        assert "Sonaro BassPro 300" in resp_b["product_title"]
        assert resp_b["category"] == "Headphones"
        assert resp_b["total_reviews"] == 69
        assert round(resp_b["average_rating"], 2) == 3.39

        # Strict distinction between A and B
        assert resp_a["product_id"] != resp_b["product_id"]
        assert resp_a["category"] != resp_b["category"]
        assert resp_a["total_reviews"] != resp_b["total_reviews"]


# ==============================================================================
# TEST 3: Semantic & Keyword Search on New Dataset
# ==============================================================================
def test_semantic_search_new_dataset():
    """Verify that searching for terms like 'laptop', 'mixer', 'phone' returns matching new dataset products."""
    search_terms = [
        ("laptop", "Laptop"),
        ("grinder", "Kitchen"),
        ("phone", "Smartphone"),
        ("bass", "Headphones"),
        ("band", "Fitness Band"),
    ]

    for term, expected_cat in search_terms:
        resp = client.get(f"/api/products/search?q={term}")
        assert resp.status_code == 200
        search_res = resp.json()
        results = search_res.get("products", [])
        assert len(results) > 0, f"Expected results for query '{term}'"
        matched_categories = [r["category"] for r in results]
        assert any(expected_cat.lower() in cat.lower() for cat in matched_categories)
        for r in results:
            assert r["product_id"].startswith("P")


# ==============================================================================
# TEST 4: Dynamic Metric Updates
# ==============================================================================
def test_dynamic_metric_updates():
    pytest.skip("Superseded by test_real_product_analysis.py::test_mandatory_test_c")


# ==============================================================================
# TEST 5: Deletion Handling -> 404 / Insufficient Review Data
# ==============================================================================
def test_deletion_handling_no_fake_fallback():
    pytest.skip("Superseded by test_mandatory_test_d — canonical 404 path")


# ==============================================================================
# TEST 6: Gemini RAG Grounding on New Dataset
# ==============================================================================
def test_gemini_rag_grounding():
    pytest.skip("Superseded by test_canonical_product_analysis.py::test_ai_summary_inputs_are_canonical_records")


# ==============================================================================
# TEST 7: Zero Legacy / Mock Data Verification
# ==============================================================================
def test_zero_legacy_or_mock_data():
    """Verify that the canonical search API never serves legacy mock IDs."""
    # Verify search API does not return legacy items
    resp = client.get("/api/products/search?q=Lego")
    assert resp.status_code == 200
    assert resp.json().get("found") is False
    assert len(resp.json().get("products", [])) == 0


# ==============================================================================
# TEST 8: Dataset Consistency (CSV == DB == 20 Products)
# ==============================================================================
def test_dataset_consistency():
    """Verify that CSV rows match Supabase canonical tables exactly (1,500 reviews, 20 products)."""
    assert CSV_PATH.exists(), f"Missing CSV dataset at {CSV_PATH}"

    # 1. Read CSV
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)

    assert len(csv_rows) == 1500, f"Expected 1,500 CSV rows, got {len(csv_rows)}"

    csv_review_ids = {r["review_id"].strip() for r in csv_rows}
    csv_product_ids = {r["product_id"].strip() for r in csv_rows}
    csv_categories = {r["category"].strip() for r in csv_rows}

    assert len(csv_review_ids) == 1500
    assert len(csv_product_ids) == 20
    assert csv_categories == {"Smartphone", "Headphones", "Laptop", "Kitchen", "Fitness Band"}

    # 2. Check Supabase canonical tables.
    # READ-ONLY CONTRACT: this is the sole direct psycopg.connect in the
    # suite that bypasses the pool. It issues only SELECT statements and
    # never writes, so no db_guard target check is required (that guard
    # covers write-capable paths). Do not add INSERT/UPDATE/DELETE here.
    import psycopg

    conn = psycopg.connect(PostgresDatabase().dsn, connect_timeout=15)
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM public.reviews")
        db_review_count = cursor.fetchone()[0]
        assert db_review_count == 1500, f"Expected 1,500 canonical reviews, got {db_review_count}"

        cursor.execute("SELECT COUNT(*) FROM public.products")
        db_product_count = cursor.fetchone()[0]
        assert db_product_count == 20, f"Expected 20 canonical products, got {db_product_count}"

        cursor.execute("SELECT source_review_id FROM public.reviews")
        db_review_ids = {row[0] for row in cursor.fetchall()}
        assert db_review_ids == csv_review_ids, "Supabase review IDs do not match CSV review IDs"

        cursor.execute("SELECT source_product_id FROM public.products")
        db_pids = {row[0] for row in cursor.fetchall()}
        assert db_pids == csv_product_ids, "Supabase product IDs do not match CSV product IDs"
    finally:
        conn.close()
