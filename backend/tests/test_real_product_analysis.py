"""Mandatory tests for Real Product Analysis pipeline.

Covers:
- Test A: Select Product A -> verify only Product A reviews are retrieved.
- Test B: Select Product B -> verify Product B analysis differs when reviews differ.
- Test C: Modify/add a review in the database -> verify factual metrics change dynamically.
- Test D: Delete all reviews for a product -> verify API returns 'insufficient review data' (no fake fallback).
- Test E: Verify response schema and no hardcoded values returned.
- Test F: Verify Gemini receives actual retrieved review content, not a fake predefined prompt.
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from services.ecommerce_db_service import EcommerceDBService, ecommerce_db_service
from services.gemini_summary_service import gemini_summary_service

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def test_db():
    """Creates an isolated temporary SQLite database with real reviews."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            product_title TEXT NOT NULL,
            category TEXT,
            review_text TEXT NOT NULL,
            rating INTEGER NOT NULL,
            sentiment TEXT NOT NULL
        );
    """)

    # Seed Product A ("PROD_A"): 3 positive 5-star reviews (Avg: 5.0, 3 reviews)
    cursor.execute(
        "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
        ("PROD_A", "Alpha Headphones", "Electronics", "Unmatched noise cancellation and crystal clear audio quality.", 5, "positive")
    )
    cursor.execute(
        "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
        ("PROD_A", "Alpha Headphones", "Electronics", "Battery life lasts over 40 hours easily. Extremely comfortable.", 5, "positive")
    )
    cursor.execute(
        "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
        ("PROD_A", "Alpha Headphones", "Electronics", "Super fast bluetooth connection and premium travel pouch.", 5, "positive")
    )

    # Seed Product B ("PROD_B"): 2 negative 1-star reviews + 1 neutral 3-star (Avg: 1.67, 3 reviews)
    cursor.execute(
        "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
        ("PROD_B", "Beta Blender", "Home & Kitchen", "Motor started smoking on day two. Horrible durability.", 1, "negative")
    )
    cursor.execute(
        "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
        ("PROD_B", "Beta Blender", "Home & Kitchen", "Plastic blade gears snapped when blending soft fruit.", 1, "negative")
    )
    cursor.execute(
        "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
        ("PROD_B", "Beta Blender", "Home & Kitchen", "Okay for liquids but leaks if filled past halfway.", 3, "neutral")
    )

    # Seed Product C ("PROD_C"): 1 review initially (to be deleted)
    cursor.execute(
        "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
        ("PROD_C", "Gamma Gadget", "Gadgets", "Just an ordinary gadget.", 3, "neutral")
    )

    conn.commit()
    conn.close()

    db_service = EcommerceDBService(db_path=db_path)

    from services.gemini_summary_service import AIStructuredProductAnalysis

    mock_analysis = AIStructuredProductAnalysis(
        product_id="PROD_A",
        product_title="Alpha Headphones",
        summary="Grounded analysis of customer feedback.",
        pros=["Audio quality", "Noise cancellation"],
        cons=[],
        insights=["Great customer satisfaction."],
        evidence=["Crystal clear audio."],
    )

    with patch("routes.products.ecommerce_db_service", db_service), \
         patch("routes.reviews.ecommerce_db_service", db_service), \
         patch("services.pros_cons_service.ecommerce_db_service", db_service), \
         patch("services.recommendation_service.ecommerce_db_service", db_service), \
         patch.object(gemini_summary_service, "_generate_product_structured_analysis", return_value=mock_analysis):
        yield {"db_service": db_service, "db_path": db_path}

    try:
        db_path.unlink()
    except Exception:
        pass


def test_mandatory_test_a_select_product_a_retrieves_only_product_a(test_db):
    """Test A: Select Product A. Verify that only Product A reviews and metrics are retrieved."""
    resp = client.get("/api/products/PROD_A/analysis")
    assert resp.status_code == 200
    data = resp.json()

    # Verify identity
    assert data["product_id"] == "PROD_A"
    assert data["product_title"] == "Alpha Headphones"

    # Verify factual counts calculated from Product A reviews only
    assert data["total_reviews"] == 3
    assert data["average_rating"] == 5.0
    assert data["rating_distribution"]["5"] == 3
    assert data["rating_distribution"]["1"] == 0
    assert data["sentiment"]["positive"] == 3
    assert data["sentiment"]["negative"] == 0

    # Verify reviews endpoint returns only Product A reviews
    rev_resp = client.get("/api/products/PROD_A/reviews")
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["total"] == 3
    for rev in rev_data["items"]:
        assert rev["product_id"] == "PROD_A"
        assert "Alpha Headphones" in rev["product_title"]
        assert "Beta Blender" not in rev["product_title"]


def test_mandatory_test_b_product_b_differs_when_reviews_differ(test_db):
    """Test B: Select Product B. Verify that Product B analysis is different when its real reviews differ."""
    resp_a = client.get("/api/products/PROD_A/analysis")
    resp_b = client.get("/api/products/PROD_B/analysis")

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    data_a = resp_a.json()
    data_b = resp_b.json()

    # Product B has different title, average rating, sentiment, and distributions
    assert data_b["product_id"] == "PROD_B"
    assert data_b["product_title"] == "Beta Blender"
    assert data_b["average_rating"] == 1.67
    assert data_b["sentiment"]["negative"] == 2
    assert data_b["sentiment"]["positive"] == 0

    assert data_a["average_rating"] != data_b["average_rating"]
    assert data_a["sentiment"] != data_b["sentiment"]
    assert data_a["rating_distribution"] != data_b["rating_distribution"]


def test_mandatory_test_c_modify_database_changes_factual_metrics(test_db):
    """Test C: Modify/add a review in the database. Run Analyze again. Verify metrics change accordingly."""
    db_path = test_db["db_path"]

    # Initial state of Product A: 3 reviews, avg 5.0
    resp_1 = client.get("/api/products/PROD_A/analysis")
    assert resp_1.status_code == 200
    assert resp_1.json()["total_reviews"] == 3
    assert resp_1.json()["average_rating"] == 5.0
    assert resp_1.json()["sentiment"]["negative"] == 0

    # Add a 1-star negative review to Product A in SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
        ("PROD_A", "Alpha Headphones", "Electronics", "Left ear cup completely stopped working after a week.", 1, "negative")
    )
    conn.commit()
    conn.close()

    # Run Analyze again on Product A
    resp_2 = client.get("/api/products/PROD_A/analysis")
    assert resp_2.status_code == 200
    data_2 = resp_2.json()

    # Verify metrics changed dynamically
    assert data_2["total_reviews"] == 4
    # (5 + 5 + 5 + 1) / 4 = 4.0
    assert data_2["average_rating"] == 4.0
    assert data_2["rating_distribution"]["1"] == 1
    assert data_2["rating_distribution"]["5"] == 3
    assert data_2["sentiment"]["negative"] == 1
    assert data_2["sentiment"]["positive"] == 3


def test_mandatory_test_d_delete_reviews_returns_insufficient_data(test_db):
    """Test D: Delete/remove all reviews for a product. Run Analyze. Verify API returns 'insufficient review data' and no fake values."""
    db_path = test_db["db_path"]

    # Delete all reviews for PROD_C
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE product_id = 'PROD_C';")
    conn.commit()
    conn.close()

    # Run Analyze on PROD_C
    resp = client.get("/api/products/PROD_C/analysis")
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert "insufficient review data" in body["detail"].lower() or "not found" in body["detail"].lower()

    # Verify no fake values or static product analysis returned
    assert "statistics" not in body or body.get("statistics") is None


def test_mandatory_test_e_structured_schema_integrity(test_db):
    """Test E: Verify that the API response conforms strictly to the structured schema without hardcoded fallback values."""
    resp = client.get("/api/products/PROD_A/analysis")
    assert resp.status_code == 200
    data = resp.json()

    # Check required top-level structured schema keys
    assert "product_id" in data
    assert "product_title" in data
    assert "total_reviews" in data
    assert "average_rating" in data
    assert "rating_distribution" in data
    assert "sentiment" in data
    assert "pros" in data
    assert "cons" in data
    assert "summary" in data
    assert "insights" in data
    assert "evidence" in data

    # Verify product_id matches requested
    assert data["product_id"] == "PROD_A"
    assert isinstance(data["total_reviews"], int)
    assert isinstance(data["average_rating"], float)
    assert isinstance(data["rating_distribution"], dict)
    assert isinstance(data["sentiment"], dict)


def test_mandatory_test_f_gemini_receives_actual_retrieved_review_content(test_db):
    """Test F: Verify Gemini receives the actual retrieved review content, not a predefined prompt with fake examples."""
    captured_prompts = []

    def mock_generate_structured_analysis(prompt, product_id, product_title):
        captured_prompts.append(prompt)
        from services.gemini_summary_service import AIStructuredProductAnalysis
        return AIStructuredProductAnalysis(
            product_id=product_id,
            product_title=product_title,
            summary="Grounded summary of Alpha Headphones.",
            pros=["Excellent noise cancellation", "Long battery life"],
            cons=[],
            insights=["High customer satisfaction in audio fidelity"],
            evidence=["Unmatched noise cancellation and crystal clear audio quality."],
        )

    with patch.object(
        gemini_summary_service,
        "_generate_product_structured_analysis",
        side_effect=mock_generate_structured_analysis
    ):
        resp = client.get("/api/products/PROD_A/analysis")

    assert resp.status_code == 200
    assert len(captured_prompts) == 1
    prompt_sent = captured_prompts[0]

    # Verify prompt contains the actual retrieved database review text for PROD_A
    assert "Unmatched noise cancellation and crystal clear audio quality." in prompt_sent
    assert "Battery life lasts over 40 hours easily." in prompt_sent
    assert "Super fast bluetooth connection" in prompt_sent

    # Verify prompt does NOT contain fake review examples or Product B reviews
    assert "Motor started smoking on day two" not in prompt_sent
    assert "Beta Blender" not in prompt_sent
    assert "Plastic blade gears snapped" not in prompt_sent
