"""Phase 5: GET /api/analytics endpoints (offline, mocked service)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from services.catalog.catalog_service import canonical_catalog
from services.evaluation_service import evaluation_service

client = TestClient(app, raise_server_exceptions=False)

OVERVIEW_AGG = {
    "total_reviews": 3,
    "average_rating": 3.0,
    "positive_reviews": 1,
    "neutral_reviews": 1,
    "negative_reviews": 1,
    "rating_distribution": {1: 0, 2: 0, 3: 1, 4: 0, 5: 1},
}

PRODUCT_ROWS = [
    {
        "source_product_id": "B000000001",
        "product_name": None,
        "review_count": 2,
        "average_rating": 4.0,
        "positive_reviews": 1,
        "neutral_reviews": 1,
        "negative_reviews": 0,
        "helpful_votes": 0,
        "review_ids": ["r1", "r2"],
    },
    {
        "source_product_id": "B000000002",
        "product_name": None,
        "review_count": 1,
        "average_rating": 1.0,
        "positive_reviews": 0,
        "neutral_reviews": 0,
        "negative_reviews": 1,
        "helpful_votes": 0,
        "review_ids": ["r3"],
    },
]


def test_overview_success():
    with patch.object(canonical_catalog, "is_configured", return_value=True), patch.object(
        canonical_catalog, "get_overview_analytics", return_value=OVERVIEW_AGG
    ):
        resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_reviews"] == 3
    assert body["positive_reviews"] == 1
    assert body["neutral_reviews"] == 1
    assert body["negative_reviews"] == 1
    assert body["average_rating"] == 3.0
    assert body["rating_distribution"]["5"] == 1


def test_overview_empty_rows():
    with patch.object(canonical_catalog, "is_configured", return_value=True), patch.object(
        canonical_catalog,
        "get_overview_analytics",
        return_value={
            "total_reviews": 0,
            "average_rating": 0.0,
            "positive_reviews": 0,
            "neutral_reviews": 0,
            "negative_reviews": 0,
            "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        },
    ):
        resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_reviews"] == 0
    assert body["average_rating"] == 0.0


def test_overview_unavailable_safe_503():
    with patch.object(canonical_catalog, "is_configured", return_value=False):
        resp = client.get("/api/analytics/overview")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Analytics service is currently unavailable. Please try again later."


def test_overview_unexpected_error_safe_503():
    secret = "INTERNAL stacktrace /etc/passwd"
    with patch.object(canonical_catalog, "is_configured", return_value=True), patch.object(
        canonical_catalog, "get_overview_analytics", side_effect=RuntimeError(secret)
    ):
        resp = client.get("/api/analytics/overview")
    assert resp.status_code == 503
    assert secret not in resp.text


def test_products_analytics_success():
    with patch.object(canonical_catalog, "is_configured", return_value=True), patch.object(
        canonical_catalog, "get_product_analytics", return_value=PRODUCT_ROWS
    ), patch.object(
        evaluation_service, "_cache", return_value={}
    ):
        resp = client.get("/api/analytics/products")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["review_count"] >= body[1]["review_count"]
    assert "average_actual_rating" in body[0]


def test_products_analytics_limit_validation():
    resp = client.get("/api/analytics/products?limit=0")
    assert resp.status_code == 422
    resp = client.get("/api/analytics/products?limit=501")
    assert resp.status_code == 422


def test_products_analytics_empty_rows():
    with patch.object(canonical_catalog, "is_configured", return_value=True), patch.object(
        canonical_catalog, "get_product_analytics", return_value=[]
    ), patch.object(
        evaluation_service, "_cache", return_value={}
    ):
        resp = client.get("/api/analytics/products")
    assert resp.status_code == 200
    assert resp.json() == []


def test_products_analytics_unavailable_safe_503():
    with patch.object(canonical_catalog, "is_configured", return_value=False):
        resp = client.get("/api/analytics/products")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Analytics service is currently unavailable. Please try again later."


def test_products_analytics_unexpected_error_safe_503():
    secret = "unexpected analytics boom"
    with patch.object(canonical_catalog, "is_configured", return_value=True), patch.object(
        canonical_catalog, "get_product_analytics", side_effect=RuntimeError(secret)
    ):
        resp = client.get("/api/analytics/products")
    assert resp.status_code == 503
    assert secret not in resp.text
