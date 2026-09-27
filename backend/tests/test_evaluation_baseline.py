"""V2-P10 tests: deterministic metric-regression baseline.

Loads backend/tests/fixtures/evaluation_baseline.json (hand-authored prediction
fixtures — never model outputs), recomputes metrics with compute_metrics(), and
asserts the result matches the recorded expected_metrics exactly. Proves the
evaluation metric implementation remains stable; it makes NO claim about model
quality or accuracy. Offline, no network, no cache, no provider.
"""

import json
from pathlib import Path

from services.evaluation_service import EVALUATION_METHODOLOGY, compute_metrics

BASELINE_PATH = Path(__file__).resolve().parent / "fixtures" / "evaluation_baseline.json"

REQUIRED_ROW_FIELDS = {
    "actual_rating",
    "predicted_rating",
    "predicted_rating_source",
    "actual_sentiment",
    "predicted_sentiment",
}


def _load() -> dict:
    assert BASELINE_PATH.is_file(), "evaluation_baseline.json must be committed"
    with BASELINE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_baseline_exists_and_declares_metric_regression_purpose():
    data = _load()
    assert data["schema_version"] == "1.0"
    purpose = data["purpose"]
    assert "metric" in purpose
    assert "not model outputs" in purpose or "NOT model outputs" in purpose
    assert "does not" in purpose


def test_baseline_predictions_are_well_formed_fixtures():
    data = _load()
    predictions = data["predictions"]
    assert isinstance(predictions, list)
    assert len(predictions) >= 8
    for row in predictions:
        assert set(row) == REQUIRED_ROW_FIELDS
        assert isinstance(row["actual_rating"], int)
        assert 1 <= row["actual_rating"] <= 5
        predicted = row["predicted_rating"]
        assert predicted is None or (isinstance(predicted, int) and 1 <= predicted <= 5)
        if predicted is None:
            assert row["predicted_rating_source"] == "not_found"
        assert row["actual_sentiment"] in {"positive", "neutral", "negative"}
        assert row["predicted_sentiment"] in {"positive", "neutral", "negative"}


def test_baseline_exercises_edge_cases():
    predictions = _load()["predictions"]
    assert any(r["predicted_rating"] is None for r in predictions), "needs a not_found row"
    assert any(
        r["predicted_rating"] is not None
        and r["predicted_rating"] != r["actual_rating"]
        for r in predictions
    ), "needs an incorrect rating row"
    assert any(
        r["predicted_sentiment"] != r["actual_sentiment"] for r in predictions
    ), "needs a sentiment mismatch row"
    ratings = {r["actual_rating"] for r in predictions}
    assert len(ratings) >= 3, "needs multiple rating classes"


def test_recomputed_metrics_match_expected_metrics():
    data = _load()
    recomputed = compute_metrics(data["predictions"])
    assert recomputed.model_dump() == data["expected_metrics"]


def test_recomputation_is_deterministic():
    data = _load()
    first = compute_metrics(data["predictions"]).model_dump()
    second = compute_metrics(data["predictions"]).model_dump()
    assert first == second
    assert first == data["expected_metrics"]


def test_baseline_methodology_matches_source_constant():
    expected = _load()["expected_metrics"]
    assert expected["methodology"] == EVALUATION_METHODOLOGY


def test_baseline_contains_no_model_or_cost_fields():
    data = _load()
    dump = json.dumps(data).lower()
    for forbidden in ("api_key", "token", "cost", "billing", "usd", "rate_limit", "provider_model"):
        assert forbidden not in dump, forbidden
