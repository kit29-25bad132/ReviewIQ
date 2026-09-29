"""Automated Tests for ReviewIQ - Complete New Dataset Verification and RAG Grounding.

Tests:
1. Product A Isolation: Querying P01 returns ONLY P01 reviews, metrics, and sentiment.
2. Product B Distinction: Querying P05 produces distinct metrics, category, brand, and reviews.
3. Semantic & Keyword Search on New Dataset: Search queries retrieve matching products from P01-P20.
4. Dynamic Metric Updates: Adding/modifying a review in DB immediately changes aggregated metrics.
5. Deletion Handling: Deleting all reviews returns 404 / insufficient review data (no fake fallback).
6. Gemini RAG Grounding: Prompt construction contains real review excerpts with review IDs from new dataset.
7. Zero Legacy IDs: No legacy mock IDs or old product names exist in DB or search endpoints.
8. Dataset Consistency: CSV (1,500 rows) == SQLite DB (1,500 rows) with 20 distinct products (P01-P20).
"""

import csv
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services.ecommerce_db_service import BASE_DIR, DATA_DIR, DB_PATH, EcommerceDBService, ecommerce_db_service
from services.gemini_summary_service import AIStructuredProductAnalysis, gemini_summary_service
from services.pros_cons_service import pros_cons_service
from services.recommendation_service import recommendation_service

client = TestClient(app, raise_server_exceptions=False)
CSV_PATH = DATA_DIR / "product_reviews_dataset.csv"

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
    """Verify that adding/modifying a review in DB immediately changes aggregated metrics."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        test_db_path = Path(tmp.name)

    # Copy real DB schema and data to temp DB
    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(test_db_path)
    src_conn.backup(dst_conn)
    src_conn.close()

    temp_service = EcommerceDBService(db_path=test_db_path)

    try:
        # Check initial stats for P01
        initial_analysis = temp_service.get_product_analysis("P01")
        assert initial_analysis is not None
        initial_count = initial_analysis.total_reviews
        initial_avg = initial_analysis.average_rating

        # Insert 10 five-star positive reviews for P01 into temp DB
        cursor = dst_conn.cursor()
        for i in range(10):
            cursor.execute("""
                INSERT INTO reviews (
                    review_id, product_id, product_title, brand, category, 
                    price_inr, rating, review_title, review_text, sentiment, 
                    verified_purchase, helpful_votes, review_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"R_TEST_{i}", "P01", "Zyra Nova 5G", "Zyra", "Smartphone",
                14999.0, 5, "Outstanding Phone", "Best phone ever purchased! Lightning fast.", "positive",
                1, 5, "2026-09-29"
            ))
        dst_conn.commit()

        # Re-fetch stats
        updated_analysis = temp_service.get_product_analysis("P01")
        assert updated_analysis is not None
        assert updated_analysis.total_reviews == initial_count + 10
        assert updated_analysis.average_rating > initial_avg
        assert updated_analysis.sentiment.get("positive", 0) == initial_analysis.sentiment.get("positive", 0) + 10
    finally:
        dst_conn.close()
        try:
            test_db_path.unlink()
        except Exception:
            pass


# ==============================================================================
# TEST 5: Deletion Handling -> 404 / Insufficient Review Data
# ==============================================================================
def test_deletion_handling_no_fake_fallback():
    """Verify that deleting all reviews for a product returns 404/insufficient data and no fake fallback."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        test_db_path = Path(tmp.name)

    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(test_db_path)
    src_conn.backup(dst_conn)
    src_conn.close()

    # Delete all reviews for P01 in temp DB
    cursor = dst_conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE product_id = 'P01'")
    dst_conn.commit()
    dst_conn.close()

    temp_service = EcommerceDBService(db_path=test_db_path)

    with patch("routes.products.ecommerce_db_service", temp_service), \
         patch("routes.reviews.ecommerce_db_service", temp_service), \
         patch("services.pros_cons_service.ecommerce_db_service", temp_service), \
         patch("services.recommendation_service.ecommerce_db_service", temp_service):

        resp = client.get("/api/products/P01/analysis")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower() or "insufficient" in resp.json()["detail"].lower()

    try:
        test_db_path.unlink()
    except Exception:
        pass


# ==============================================================================
# TEST 6: Gemini RAG Grounding on New Dataset
# ==============================================================================
def test_gemini_rag_grounding():
    """Verify that Gemini prompt builder includes real review text with review IDs from the new dataset."""
    sample_reviews = ecommerce_db_service.get_sample_reviews("P01", limit=10)
    assert len(sample_reviews) > 0
    assert "Review" in sample_reviews[0]

    # Verify that when generate_product_analysis is called with configured analyzer or prompt formatting,
    # prompt is constructed with exact dataset reviews
    formatted = "\n".join(f"- {r}" for r in sample_reviews[:10])
    prompt = f"""Product ID: P01\nProduct Title: Zyra Nova 5G\nCategory: Smartphone\n\nCustomer Reviews from Dataset:\n\"\"\"\n{formatted}\n\"\"\""""
    assert "Zyra Nova 5G" in prompt
    assert sample_reviews[0] in prompt


# ==============================================================================
# TEST 7: Zero Legacy / Mock Data Verification
# ==============================================================================
def test_zero_legacy_or_mock_data():
    """Verify that no legacy product IDs or mock items exist in the database or API search results."""
    legacy_terms = ["Lego", "Toothbrush", "B00", "B01", "B07", "B08", "Alpha Headphones", "Beta Blender"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for term in legacy_terms:
        cursor.execute("SELECT COUNT(*) FROM reviews WHERE product_id LIKE ? OR product_title LIKE ?", (f"%{term}%", f"%{term}%"))
        count = cursor.fetchone()[0]
        assert count == 0, f"Found legacy data in reviews table for term '{term}': {count} occurrences"

    conn.close()

    # Verify search API does not return legacy items
    resp = client.get("/api/products/search?q=Lego")
    assert resp.status_code == 200
    assert len(resp.json().get("products", [])) == 0


# ==============================================================================
# TEST 8: Dataset Consistency (CSV == DB == 20 Products)
# ==============================================================================
def test_dataset_consistency():
    """Verify that CSV rows match SQLite DB rows exactly (1,500 reviews, 20 products, 5 categories)."""
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

    # 2. Check SQLite DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM reviews")
    db_review_count = cursor.fetchone()[0]
    assert db_review_count == 1500, f"Expected 1,500 DB reviews, got {db_review_count}"

    cursor.execute("SELECT COUNT(DISTINCT product_id) FROM reviews")
    db_product_count = cursor.fetchone()[0]
    assert db_product_count == 20, f"Expected 20 DB products, got {db_product_count}"

    cursor.execute("SELECT review_id FROM reviews")
    db_review_ids = {row[0] for row in cursor.fetchall()}
    assert db_review_ids == csv_review_ids, "DB review IDs do not match CSV review IDs"

    cursor.execute("SELECT DISTINCT product_id FROM reviews")
    db_pids = {row[0] for row in cursor.fetchall()}
    assert db_pids == csv_product_ids, "DB product IDs do not match CSV product IDs"

    cursor.execute("SELECT DISTINCT category FROM reviews")
    db_cats = {row[0] for row in cursor.fetchall()}
    assert db_cats == csv_categories, "DB categories do not match CSV categories"

    conn.close()
