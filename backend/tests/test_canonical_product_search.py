"""Phase 3 Task 1: canonical product search cutover (live Supabase, no mocks for data).

Verifies GET /api/products/search is served by CanonicalCatalogService:
- name / brand / category matching against canonical P01-P20 data
- empty-query and limit behavior preserved
- empty results keep the found=False contract
- invalid inputs rejected (422)
- canonical DB outage -> honest 503, DB errors -> honest 500
- legacy SQLite is never consulted on the search path
"""

from unittest.mock import patch
from pathlib import Path

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


def _assert_no_sqlite_fallback():
    return patch.object(
        sqlite_module.ecommerce_db_service,
        "search_products",
        side_effect=AssertionError("legacy SQLite fallback used on search path"),
    )


def test_search_by_product_name_returns_canonical_ids():
    with _assert_no_sqlite_fallback():
        resp = client.get("/api/products/search", params={"q": "Kelto Gamer"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    ids = [p["product_id"] for p in body["products"]]
    assert "P12" in ids
    for p in body["products"]:
        assert p["product_id"].startswith("P")
        assert isinstance(p["product_title"], str) and p["product_title"]
        assert isinstance(p["review_count"], int) and p["review_count"] > 0
        assert isinstance(p["average_rating"], (int, float)) and p["average_rating"] > 0


def test_search_by_brand_returns_all_brand_products():
    with _assert_no_sqlite_fallback():
        resp = client.get("/api/products/search", params={"q": "Kelto"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    ids = {p["product_id"] for p in body["products"]}
    assert {"P02", "P07", "P12"} <= ids


def test_search_by_category_returns_category_products():
    with _assert_no_sqlite_fallback():
        resp = client.get("/api/products/search", params={"q": "Laptop"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    ids = {p["product_id"] for p in body["products"]}
    assert ids == {"P09", "P10", "P11", "P12"}
    assert all(p["category"] == "Laptop" for p in body["products"])


def test_search_empty_query_returns_top_products():
    with _assert_no_sqlite_fallback():
        resp = client.get("/api/products/search")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert len(body["products"]) > 0


def test_search_limit_is_respected():
    with _assert_no_sqlite_fallback():
        resp = client.get("/api/products/search", params={"q": "a", "limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()["products"]) <= 2


def test_search_unknown_product_returns_empty_result():
    with _assert_no_sqlite_fallback():
        resp = client.get("/api/products/search", params={"q": "NONEXISTENT_99999"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["products"] == []
    assert body["message"]


def test_search_invalid_limit_returns_422():
    assert client.get("/api/products/search", params={"limit": 0}).status_code == 422
    assert client.get("/api/products/search", params={"limit": 101}).status_code == 422


def test_search_unconfigured_catalog_returns_503():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(canonical_catalog, "is_configured", return_value=False):
        resp = no_raise_client.get("/api/products/search", params={"q": "Kelto"})
    assert resp.status_code == 503
    assert "detail" in resp.json()


def test_search_database_error_is_not_masked_by_fallback():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(
        canonical_catalog, "get_products", side_effect=RuntimeError("supabase down")
    ), _assert_no_sqlite_fallback():
        resp = no_raise_client.get("/api/products/search", params={"q": "Kelto"})
    assert resp.status_code == 500
