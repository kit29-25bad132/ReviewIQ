"""Phase 5: GET /api/dataset/reviews API tests (offline, mocked service)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from models.dataset import DatasetReview
from services.dataset_service import DatasetUnavailableError, dataset_service

client = TestClient(app, raise_server_exceptions=False)

SAMPLE_ROWS = [
    DatasetReview(
        id="abc123",
        asin="B000000001",
        product_name="Test Phone",
        review_text="Great battery life for the price.",
        actual_rating=5,
        summary="Great battery",
        actual_sentiment="positive",
    ),
    DatasetReview(
        id="def456",
        asin="B000000002",
        product_name="Other Item",
        review_text="Terrible camera quality.",
        actual_rating=1,
        summary="Bad camera",
        actual_sentiment="negative",
    ),
]


def test_dataset_reviews_default_parameters():
    with patch.object(dataset_service, "query", return_value=(SAMPLE_ROWS, 2)) as mock_query:
        resp = client.get("/api/dataset/reviews")
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] == "abc123"
    mock_query.assert_called_once_with(20, 0, None, None, None, None)


def test_dataset_reviews_limit_and_offset():
    with patch.object(dataset_service, "query", return_value=([], 0)) as mock_query:
        resp = client.get("/api/dataset/reviews?limit=5&offset=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 5
    assert body["offset"] == 10
    mock_query.assert_called_once_with(5, 10, None, None, None, None)


def test_dataset_reviews_search_and_filters():
    with patch.object(dataset_service, "query", return_value=([SAMPLE_ROWS[0]], 1)) as mock_query:
        resp = client.get(
            "/api/dataset/reviews?search=battery&rating=5&sentiment=positive&product=B00000"
        )
    assert resp.status_code == 200
    mock_query.assert_called_once_with(20, 0, "battery", 5, "positive", "B00000")


def test_dataset_reviews_empty_result():
    with patch.object(dataset_service, "query", return_value=([], 0)):
        resp = client.get("/api/dataset/reviews?search=nothing-matches-this")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_dataset_unavailable_returns_safe_503():
    secret = "SQLITE_CORRUPT at /var/secrets/path table=reviews"
    with patch.object(
        dataset_service, "query", side_effect=DatasetUnavailableError(secret)
    ):
        resp = client.get("/api/dataset/reviews")
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert secret not in resp.text
    assert detail == "Review dataset is currently unavailable. Please try again later."


def test_dataset_unexpected_error_returns_safe_503():
    secret = "UNEXPECTED internal dump token=sk-xyz"
    with patch.object(dataset_service, "query", side_effect=RuntimeError(secret)):
        resp = client.get("/api/dataset/reviews")
    assert resp.status_code == 503
    assert secret not in resp.text
    assert resp.json()["detail"] == "Review dataset is currently unavailable. Please try again later."


def test_dataset_invalid_limit_returns_422():
    resp = client.get("/api/dataset/reviews?limit=0")
    assert resp.status_code == 422


def test_dataset_limit_over_max_returns_422():
    resp = client.get("/api/dataset/reviews?limit=101")
    assert resp.status_code == 422


def test_dataset_invalid_rating_returns_422():
    resp = client.get("/api/dataset/reviews?rating=6")
    assert resp.status_code == 422


def test_dataset_invalid_sentiment_returns_422():
    resp = client.get("/api/dataset/reviews?sentiment=happy")
    assert resp.status_code == 422


def test_dataset_invalid_offset_returns_422():
    resp = client.get("/api/dataset/reviews?offset=-1")
    assert resp.status_code == 422
