import os
from pathlib import Path
import pytest
from dotenv import dotenv_values
from services.catalog.catalog_service import canonical_catalog

@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def test_scan_current_catalog_state():
    scan = canonical_catalog.scan_current_catalog_state()
    assert scan.database_connected is True
    assert scan.total_products == 20
    assert scan.total_reviews == 1500
    assert scan.orphan_reviews_count == 0
    assert len(scan.categories) == 5
    assert len(scan.brands) == 11
    assert "Smartphone" in scan.categories
    assert "Laptop" in scan.categories
    assert "Kelto" in scan.brands


def test_get_products():
    products, total = canonical_catalog.get_products(limit=50)
    assert total == 20
    assert len(products) == 20
    
    # Check first product
    p1 = products[0]
    assert "product_id" in p1
    assert "product_title" in p1
    assert "brand" in p1
    assert "category" in p1
    assert "review_count" in p1
    assert "average_rating" in p1
    assert p1["review_count"] > 0
    assert p1["average_rating"] > 0


def test_get_products_filtered_by_category():
    laptops, total = canonical_catalog.get_products(category="Laptop")
    assert total == 4
    for l in laptops:
        assert l["category"] == "Laptop"


def test_get_product_by_id():
    # Kelto Gamer 16 (P12)
    kelto = canonical_catalog.get_product_by_id("P12")
    assert kelto is not None
    assert kelto["source_product_id"] == "P12"
    assert "Kelto Gamer" in kelto["product_title"]
    assert kelto["brand"] == "Kelto"
    assert kelto["category"] == "Laptop"
    assert kelto["review_count"] == 95


def test_get_product_statistics():
    stats = canonical_catalog.get_product_statistics("P12")
    assert stats is not None
    assert stats["total_reviews"] == 95
    assert stats["average_rating"] > 0
    assert "rating_distribution" in stats
    assert "sentiment_distribution" in stats
    assert stats["verified_purchase_percentage"] >= 0.0


def test_get_reviews_paginated():
    reviews, total = canonical_catalog.get_reviews("P12", page=1, page_size=10)
    assert total == 95
    assert len(reviews) == 10
    r0 = reviews[0]
    assert r0["product_id"] == "P12"
    assert "review_text" in r0
    assert 1 <= r0["rating"] <= 5
    assert "source_dataset" in r0
    assert r0["source_dataset"] == "product_reviews_dataset.csv"
