"""Phase 5: GET /api/analytics endpoints (offline, mocked service)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from models.dataset import DatasetReview
from services.dataset_service import DatasetUnavailableError, dataset_service
from services.evaluation_service import evaluation_service

client = TestClient(app, raise_server_exceptions=False)

ROWS = [
    DatasetReview(
        id="r1",
        asin="B000000001",
        review_text="Love it",
        actual_rating=5,
        actual_sentiment="positive",
    ),
    DatasetReview(
        id="r2",
        asin="B000000001",
        review_text="Okay",
        actual_rating=3,
        actual_sentiment="neutral",
    ),
    DatasetReview(
        id="r3",
        asin="B000000002",
        review_text="Hate it",
        actual_rating=1,
        actual_sentiment="negative",
    ),
]


def test_overview_success():
    with patch.object(dataset_service, "records", return_value=ROWS):
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
    with patch.object(dataset_service, "records", return_value=[]):
        resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_reviews"] == 0
    assert body["average_rating"] == 0.0


def test_overview_unavailable_safe_503():
    secret = "DB password=hunter2 connection failed"
    with patch.object(
        dataset_service, "records", side_effect=DatasetUnavailableError(secret)
    ):
        resp = client.get("/api/analytics/overview")
    assert resp.status_code == 503
    assert secret not in resp.text
    assert resp.json()["detail"] == "Analytics service is currently unavailable. Please try again later."


def test_overview_unexpected_error_safe_503():
    secret = "INTERNAL stacktrace /etc/passwd"
    with patch.object(dataset_service, "records", side_effect=RuntimeError(secret)):
        resp = client.get("/api/analytics/overview")
    assert resp.status_code == 503
    assert secret not in resp.text


def test_products_analytics_success():
    with patch.object(dataset_service, "records", return_value=ROWS), patch.object(
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
    with patch.object(dataset_service, "records", return_value=[]), patch.object(
        evaluation_service, "_cache", return_value={}
    ):
        resp = client.get("/api/analytics/products")
    assert resp.status_code == 200
    assert resp.json() == []


def test_products_analytics_unavailable_safe_503():
    secret = "sqlite disk I/O error /secret/path.db"
    with patch.object(
        dataset_service, "records", side_effect=DatasetUnavailableError(secret)
    ):
        resp = client.get("/api/analytics/products")
    assert resp.status_code == 503
    assert secret not in resp.text
    assert resp.json()["detail"] == "Analytics service is currently unavailable. Please try again later."


def test_products_analytics_unexpected_error_safe_503():
    secret = "unexpected analytics boom"
    with patch.object(dataset_service, "records", side_effect=RuntimeError(secret)):
        resp = client.get("/api/analytics/products")
    assert resp.status_code == 503
    assert secret not in resp.text
