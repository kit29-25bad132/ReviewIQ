"""End-to-End Runtime Unification Tests across all ReviewIQ APIs."""

import pytest
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def test_products_search_kelto():
    response = client.get("/api/products/search?q=Kelto")
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    products = data["products"]
    assert len(products) >= 3
    product_ids = [p["product_id"] for p in products]
    assert "P12" in product_ids  # Kelto Gamer 16
    assert "P02" in product_ids  # Kelto Pixel Lite
    assert "P07" in product_ids  # Kelto SoundMax ANC


def test_product_analysis_p12_kelto_gamer():
    response = client.get("/api/products/P12/analysis")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "P12"
    assert "Kelto Gamer" in data["product_title"]
    assert data["category"] == "Laptop"
    assert data["total_reviews"] == 95
    assert data["average_rating"] > 0
    assert "rating_distribution" in data
    assert "sentiment" in data
    assert len(data["recent_reviews"]) > 0


def test_product_pros_cons_p12():
    response = client.get("/api/products/P12/pros-cons")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "P12"
    assert "Kelto Gamer" in data["product_title"]
    assert data["total_analyzed_reviews"] == 95
    assert len(data["pros"]) > 0


def test_product_reviews_paginated_p12():
    response = client.get("/api/products/P12/reviews?page=1&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 95
    assert len(data["items"]) == 20
    assert data["page"] == 1
    assert data["limit"] == 20


def test_unknown_product_returns_404():
    response = client.get("/api/products/NONEXISTENT_99999/analysis")
    assert response.status_code == 404
