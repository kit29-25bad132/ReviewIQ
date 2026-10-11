"""Phase 3 Task 3: canonical reviews + pros/cons cutover (live Supabase).

Verifies GET /api/products/{id}/reviews and /pros-cons (/theme-reviews)
are served from the canonical catalog:
- P12 returns 95 canonical reviews with stable IDs and correct mapping
- pagination is stable and duplicate-free; filters work
- unknown products return 404; DB errors never fall back to SQLite
- pros/cons aggregate only canonical reviews with verbatim evidence
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from services import ecommerce_db_service as sqlite_module

client = TestClient(app)
no_raise_client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def _no_sqlite_reviews():
    return patch.object(
        sqlite_module.ecommerce_db_service,
        "get_product_reviews",
        side_effect=AssertionError("legacy SQLite fallback used on reviews path"),
    )


def _no_sqlite_pros_cons():
    return patch.object(
        sqlite_module.ecommerce_db_service,
        "_get_connection",
        side_effect=AssertionError("legacy SQLite fallback used on pros/cons path"),
    )


def test_p12_reviews_total_and_mapping():
    with _no_sqlite_reviews():
        resp = client.get("/api/products/P12/reviews", params={"page": 1, "limit": 20})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 95
    assert len(body["items"]) == 20
    assert body["page"] == 1
    assert body["limit"] == 20
    assert body["total_pages"] == 5
    ids = [r["id"] for r in body["items"]]
    assert len(set(ids)) == 20
    for r in body["items"]:
        assert isinstance(r["id"], str) and r["id"].startswith("R")
        assert r["product_id"] == "P12"
        assert "Kelto Gamer" in r["product_title"]
        assert r["category"] == "Laptop"
        assert r["review_text"]
        assert 1 <= r["rating"] <= 5
        assert r["sentiment"] in ("positive", "neutral", "negative")


def test_p12_reviews_pagination_has_no_duplicates():
    with _no_sqlite_reviews():
        p1 = client.get("/api/products/P12/reviews", params={"page": 1, "limit": 50}).json()
        p2 = client.get("/api/products/P12/reviews", params={"page": 2, "limit": 50}).json()
    assert p1["total"] == 95 and p2["total"] == 95
    ids1 = {r["id"] for r in p1["items"]}
    ids2 = {r["id"] for r in p2["items"]}
    assert len(ids1) == 50 and len(ids2) == 45
    assert not (ids1 & ids2)
    assert len(ids1 | ids2) == 95


def test_p12_reviews_filters():
    with _no_sqlite_reviews():
        five = client.get("/api/products/P12/reviews", params={"rating": 5, "limit": 100}).json()
        pos = client.get("/api/products/P12/reviews", params={"sentiment": "positive", "limit": 100}).json()
    assert five["total"] == 32
    assert all(r["rating"] == 5 for r in five["items"])
    assert pos["total"] == 52
    assert all(r["sentiment"] == "positive" for r in pos["items"])


def test_unknown_product_reviews_returns_404():
    with _no_sqlite_reviews():
        resp = client.get("/api/products/NONEXISTENT_99999/reviews")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_valid_product_without_reviews_returns_empty_page():
    from services.catalog.catalog_service import canonical_catalog

    product = {
        "id": "00000000-0000-0000-0000-000000000000",
        "source_product_id": "PXX",
        "product_title": "Ghost Product",
        "category": "Laptop",
    }
    with patch.object(canonical_catalog, "get_product_by_id", return_value=product), patch.object(
        canonical_catalog, "get_reviews", return_value=([], 0)
    ), _no_sqlite_reviews():
        resp = client.get("/api/products/PXX/reviews")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["total_pages"] == 0


def test_reviews_unconfigured_returns_503():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(canonical_catalog, "is_configured", return_value=False):
        resp = no_raise_client.get("/api/products/P12/reviews")
    assert resp.status_code == 503
    assert "detail" in resp.json()


def test_reviews_database_error_is_not_masked():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(
        canonical_catalog, "get_product_by_id", side_effect=RuntimeError("supabase down")
    ), _no_sqlite_reviews():
        resp = no_raise_client.get("/api/products/P12/reviews")
    assert resp.status_code == 500


def test_p12_pros_cons_from_canonical_reviews():
    with _no_sqlite_pros_cons():
        resp = client.get("/api/products/P12/pros-cons")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "P12"
    assert "Kelto Gamer" in data["product_title"]
    assert data["total_analyzed_reviews"] == 95
    assert len(data["pros"]) > 0
    # Every example and evidence ID traces to a canonical record.
    from services.catalog.catalog_service import canonical_catalog
    pool, _ = canonical_catalog.get_reviews("P12", page=1, page_size=5000)
    texts = {r["review_text"] for r in pool}
    ids = {r["source_review_id"] for r in pool}
    for theme in data["pros"] + data["cons"]:
        assert 0 < theme["percentage"] <= 100
        for ex in theme["example_reviews"]:
            assert ex in texts
        for eid in theme["evidence_review_ids"]:
            assert eid in ids


def test_pros_cons_unknown_product_returns_404():
    with _no_sqlite_pros_cons():
        resp = client.get("/api/products/NONEXISTENT_99999/pros-cons")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_pros_cons_unconfigured_returns_503():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(canonical_catalog, "is_configured", return_value=False):
        resp = no_raise_client.get("/api/products/P12/pros-cons")
    assert resp.status_code == 503


def test_theme_reviews_from_canonical_reviews():
    with _no_sqlite_pros_cons():
        resp = client.get(
            "/api/products/P12/theme-reviews",
            params={"theme": "Quality & Durability", "limit": 10},
        )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) > 0
    keywords = ["quality", "durable", "solid", "well made", "excellent", "sturdy", "premium"]
    for r in items:
        assert r["product_id"] == "P12"
        assert isinstance(r["id"], str) and r["id"].startswith("R")
        assert any(kw in r["review_text"].lower() for kw in keywords)


def test_theme_reviews_unknown_product_returns_empty():
    with _no_sqlite_pros_cons():
        resp = client.get(
            "/api/products/NONEXISTENT_99999/theme-reviews",
            params={"theme": "Quality & Durability"},
        )
    assert resp.status_code == 200
    assert resp.json() == []
