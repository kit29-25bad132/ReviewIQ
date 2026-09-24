"""Phase 5: GET /api/evaluation and POST /api/evaluation/run (mocked, no live Gemini)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from models.dataset import EvaluationMetrics
from services.dataset_service import DatasetUnavailableError
from services.evaluation_service import evaluation_service

client = TestClient(app, raise_server_exceptions=False)

METRICS = EvaluationMetrics(
    evaluated_reviews=10,
    rating_accuracy=0.8,
    rating_mae=0.4,
    sentiment_accuracy=0.9,
    confusion_matrix=[[0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 8, 2], [0, 0, 0, 1, 9]],
    methodology="offline fixture",
)


def test_get_evaluation_returns_cached_metrics():
    with patch.object(evaluation_service, "metrics", return_value=METRICS):
        resp = client.get("/api/evaluation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["evaluated_reviews"] == 10
    assert body["rating_accuracy"] == 0.8


def test_get_evaluation_empty_returns_null():
    with patch.object(evaluation_service, "metrics", return_value=None):
        resp = client.get("/api/evaluation")
    assert resp.status_code == 200
    assert resp.json() is None


def test_run_evaluation_success_with_mocked_service():
    with patch.object(evaluation_service, "run", return_value=METRICS) as mock_run:
        resp = client.post("/api/evaluation/run?limit=5")
    assert resp.status_code == 200
    assert resp.json()["evaluated_reviews"] == 10
    mock_run.assert_called_once_with(limit=5, reanalyze=False)


def test_run_evaluation_invalid_limit_returns_422():
    resp = client.post("/api/evaluation/run?limit=0")
    assert resp.status_code == 422
    resp = client.post("/api/evaluation/run?limit=5000")
    assert resp.status_code == 422


def test_run_evaluation_dataset_unavailable_safe_503():
    secret = "csv path /secret/data.csv missing columns internal"
    with patch.object(
        evaluation_service, "run", side_effect=DatasetUnavailableError(secret)
    ):
        resp = client.post("/api/evaluation/run")
    assert resp.status_code == 503
    assert secret not in resp.text
    assert (
        resp.json()["detail"]
        == "Evaluation dataset is currently unavailable. Please try again later."
    )


def test_run_evaluation_value_error_safe_503():
    secret = "AI analysis is temporarily unavailable. gemini key=AIzaFake"
    with patch.object(evaluation_service, "run", side_effect=ValueError(secret)):
        resp = client.post("/api/evaluation/run")
    assert resp.status_code == 503
    assert secret not in resp.text
    assert (
        resp.json()["detail"]
        == "Evaluation service is temporarily unavailable. Please try again later."
    )


def test_run_evaluation_unexpected_error_safe_503():
    secret = "RuntimeError: evaluation boom stack=..."
    with patch.object(evaluation_service, "run", side_effect=RuntimeError(secret)):
        resp = client.post("/api/evaluation/run")
    assert resp.status_code == 503
    assert secret not in resp.text
    assert (
        resp.json()["detail"]
        == "Evaluation service is temporarily unavailable. Please try again later."
    )
