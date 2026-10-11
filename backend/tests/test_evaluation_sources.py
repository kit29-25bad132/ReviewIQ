"""Phase 3 Task 5.3: evaluation source separation, versioning, reproducibility.

All tests are offline: the AI provider entry point
(`analyzer_service.analyze_review`) is mocked and call-counted, and the
results cache is redirected to tmp_path so the repository cache is never
touched. No live provider calls, no 1500-record runs.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services.evaluation_service import (
    CANONICAL_SOURCE,
    EvaluationService,
    has_valid_prediction,
)

client = TestClient(app, raise_server_exceptions=False)


def _ai_result(rating=5, sentiment="positive"):
    return SimpleNamespace(
        rating=rating,
        rating_source="explicit",
        sentiment=sentiment,
        pros=[],
        cons=[],
        summary="mocked summary",
    )


def _bench_record(rid, text="benchmark text", rating=5, sentiment="positive"):
    return SimpleNamespace(id=rid, review_text=text, actual_rating=rating, actual_sentiment=sentiment)


def _canon_row(rid, text="canonical text", rating=5, sentiment="positive"):
    return {"id": rid, "review_text": text, "actual_rating": rating, "actual_sentiment": sentiment}


def _service(tmp_path):
    svc = EvaluationService()
    svc.path = tmp_path / "results.json"
    return svc


def _seed(svc, mapping):
    import json
    svc.path.parent.mkdir(parents=True, exist_ok=True)
    svc.path.write_text(json.dumps(mapping), encoding="utf-8")


def _bench_entry(rid, predicted=5, with_meta=True):
    entry = {
        "actual_rating": 5,
        "predicted_rating": predicted,
        "actual_sentiment": "positive",
        "predicted_sentiment": "positive",
    }
    if with_meta:
        entry.update({"source": "benchmark", "dataset_version": "csv-abc123"})
    return entry


# ---------------- API contract (service level) ----------------

def test_default_source_is_benchmark(tmp_path):
    svc = _service(tmp_path)
    records = [_bench_record("R1"), _bench_record("R2")]
    with patch("services.evaluation_service.dataset_service") as mock_ds, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_ds.records.return_value = records
        mock_ai.is_configured.return_value = True
        mock_ai.analyze_review.side_effect = lambda text: _ai_result()
        metrics = svc.run(limit=2)
    assert metrics.evaluated_reviews == 2
    assert mock_ai.analyze_review.call_count == 2
    cache = svc._cache()
    assert set(cache.keys()) == {"R1", "R2"}
    assert cache["R1"]["source"] == "benchmark"


def test_explicit_canonical_source_uses_catalog_records(tmp_path):
    svc = _service(tmp_path)
    rows = [_canon_row("R1", text="canonical one"), _canon_row("R2", text="canonical two")]
    with patch("services.evaluation_service.dataset_service") as mock_ds, patch(
        "services.catalog.catalog_service.canonical_catalog"
    ) as mock_cat, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_cat.is_configured.return_value = True
        mock_cat.query_dataset_reviews.return_value = (rows, 2)
        mock_cat.get_dataset_version.return_value = "hash_vers1"
        mock_ai.is_configured.return_value = True
        mock_ai.analyze_review.side_effect = lambda text: _ai_result()
        metrics = svc.run(limit=2, source="canonical")
    assert metrics.evaluated_reviews == 2
    analyzed_texts = [c.args[0] for c in mock_ai.analyze_review.call_args_list]
    assert analyzed_texts == ["canonical one", "canonical two"]
    mock_ds.records.assert_not_called()
    cache = svc._cache()
    assert set(cache.keys()) == {"canonical::hash_vers1::R1", "canonical::hash_vers1::R2"}


def test_unsupported_source_rejected_at_service_level(tmp_path):
    svc = _service(tmp_path)
    with pytest.raises(ValueError):
        svc.run(source="sqlite")
    with pytest.raises(ValueError):
        svc.metrics(source="legacy")


def test_canonical_unconfigured_is_honest_and_call_free(tmp_path):
    svc = _service(tmp_path)
    from services.dataset_service import DatasetUnavailableError
    with patch(
        "services.catalog.catalog_service.canonical_catalog"
    ) as mock_cat, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_cat.is_configured.return_value = False
        mock_ai.analyze_review.side_effect = AssertionError("provider must not be called")
        with pytest.raises(DatasetUnavailableError):
            svc.run(source="canonical")
        assert svc.metrics(source="canonical") is None


# ---------------- cache isolation and versioning ----------------

def test_identical_ids_do_not_collide_across_sources(tmp_path):
    svc = _service(tmp_path)
    _seed(svc, {
        "R1": _bench_entry("R1", predicted=5),
        "canonical::v1::R1": {
            "actual_rating": 1, "predicted_rating": 1,
            "actual_sentiment": "negative", "predicted_sentiment": "negative",
            "source": "canonical", "dataset_version": "v1",
        },
    })
    bench = svc.metrics(source="benchmark")
    assert bench.evaluated_reviews == 1
    assert bench.rating_accuracy == 1.0
    with patch(
        "services.catalog.catalog_service.canonical_catalog"
    ) as mock_cat:
        mock_cat.is_configured.return_value = True
        mock_cat.get_dataset_version.return_value = "v1"
        canon = svc.metrics(source="canonical")
    assert canon.evaluated_reviews == 1
    assert canon.rating_accuracy == 1.0
    # Different labels per source prove isolation (benchmark 5/positive vs canonical 1/negative).
    assert bench.sentiment_accuracy == 1.0 and canon.sentiment_accuracy == 1.0


def test_dataset_version_change_does_not_reuse_results(tmp_path):
    svc = _service(tmp_path)
    _seed(svc, {
        "canonical::v1::R1": {
            "actual_rating": 5, "predicted_rating": 5,
            "actual_sentiment": "positive", "predicted_sentiment": "positive",
            "source": "canonical", "dataset_version": "v1",
        },
    })
    with patch(
        "services.catalog.catalog_service.canonical_catalog"
    ) as mock_cat, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_cat.is_configured.return_value = True
        mock_cat.get_dataset_version.return_value = "v2"
        mock_ai.is_configured.return_value = True
        mock_ai.analyze_review.side_effect = lambda text: _ai_result()
        assert svc.metrics(source="canonical") is None
        rows = [_canon_row("R1")]
        mock_cat.query_dataset_reviews.return_value = (rows, 1)
        svc.run(source="canonical")
    assert mock_ai.analyze_review.call_count == 1
    assert "canonical::v2::R1" in svc._cache()
    assert "canonical::v1::R1" in svc._cache()  # history preserved, not rewritten


def test_legacy_entries_follow_compatibility_rule(tmp_path):
    svc = _service(tmp_path)
    _seed(svc, {"R9": _bench_entry("R9", with_meta=False)})
    bench = svc.metrics(source="benchmark")
    assert bench is not None and bench.evaluated_reviews == 1
    with patch(
        "services.catalog.catalog_service.canonical_catalog"
    ) as mock_cat:
        mock_cat.is_configured.return_value = True
        mock_cat.get_dataset_version.return_value = "v9"
        assert svc.metrics(source="canonical") is None


def test_repeated_metrics_do_not_rewrite_cache(tmp_path):
    svc = _service(tmp_path)
    _seed(svc, {"R1": _bench_entry("R1")})
    before = svc.path.read_bytes()
    assert svc.metrics(source="benchmark").evaluated_reviews == 1
    assert svc.metrics(source="benchmark").evaluated_reviews == 1
    assert svc.path.read_bytes() == before


# ---------------- reproducibility and provider-call control ----------------

def test_metrics_make_zero_provider_calls(tmp_path):
    svc = _service(tmp_path)
    _seed(svc, {"R1": _bench_entry("R1")})
    with patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_ai.analyze_review.side_effect = AssertionError("provider must not be called")
        assert svc.metrics(source="benchmark").evaluated_reviews == 1


def test_fully_cached_rerun_makes_zero_provider_calls(tmp_path):
    svc = _service(tmp_path)
    records = [_bench_record("R1"), _bench_record("R2")]
    with patch("services.evaluation_service.dataset_service") as mock_ds, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_ds.records.return_value = records
        mock_ai.is_configured.return_value = True
        mock_ai.analyze_review.side_effect = lambda text: _ai_result()
        svc.run()
        assert mock_ai.analyze_review.call_count == 2
        mock_ai.analyze_review.reset_mock()
        mock_ai.analyze_review.side_effect = AssertionError("provider must not be called")
        rerun = svc.run()
    assert rerun.evaluated_reviews == 2
    mock_ai.analyze_review.assert_not_called()


def test_only_missing_records_are_analyzed(tmp_path):
    svc = _service(tmp_path)
    _seed(svc, {"R1": _bench_entry("R1", predicted=5)})
    records = [_bench_record("R1"), _bench_record("R2", text="needs analysis")]
    with patch("services.evaluation_service.dataset_service") as mock_ds, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_ds.records.return_value = records
        mock_ai.is_configured.return_value = True
        mock_ai.analyze_review.side_effect = lambda text: _ai_result()
        svc.run()
    analyzed = [c.args[0] for c in mock_ai.analyze_review.call_args_list]
    assert analyzed == ["needs analysis"]


def test_invalid_predictions_are_treated_as_missing(tmp_path):
    assert not has_valid_prediction({"predicted_rating": None})
    assert not has_valid_prediction({"predicted_rating": 9})
    assert not has_valid_prediction({"predicted_rating": "5"})
    assert has_valid_prediction({"predicted_rating": 3})
    svc = _service(tmp_path)
    _seed(svc, {"R1": _bench_entry("R1", predicted=None)})
    records = [_bench_record("R1", text="retry me")]
    with patch("services.evaluation_service.dataset_service") as mock_ds, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_ds.records.return_value = records
        mock_ai.is_configured.return_value = True
        mock_ai.analyze_review.side_effect = lambda text: _ai_result()
        metrics = svc.run()
    assert mock_ai.analyze_review.call_count == 1
    assert metrics.rating_accuracy == 1.0


def test_reanalyze_forces_refresh_with_explicit_flag(tmp_path):
    svc = _service(tmp_path)
    records = [_bench_record("R1")]
    with patch("services.evaluation_service.dataset_service") as mock_ds, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_ds.records.return_value = records
        mock_ai.is_configured.return_value = True
        mock_ai.analyze_review.side_effect = lambda text: _ai_result()
        svc.run()
        assert mock_ai.analyze_review.call_count == 1
        svc.run()
        assert mock_ai.analyze_review.call_count == 1
        svc.run(reanalyze=True)
        assert mock_ai.analyze_review.call_count == 2


def test_metrics_only_endpoint_makes_zero_provider_calls(tmp_path, monkeypatch):
    import routes.evaluation as eval_route

    svc = _service(tmp_path)
    _seed(svc, {"R1": _bench_entry("R1")})
    monkeypatch.setattr(eval_route, "evaluation_service", svc)
    with patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_ai.analyze_review.side_effect = AssertionError("provider must not be called")
        resp = client.get("/api/evaluation")
    assert resp.status_code == 200
    assert resp.json()["evaluated_reviews"] == 1


# ---------------- data correctness ----------------

def test_records_aligned_by_stable_identity(tmp_path):
    svc = _service(tmp_path)
    records = [
        _bench_record("R2", text="second", rating=1, sentiment="negative"),
        _bench_record("R1", text="first", rating=5, sentiment="positive"),
    ]
    with patch("services.evaluation_service.dataset_service") as mock_ds, patch(
        "services.evaluation_service.analyzer_service"
    ) as mock_ai:
        mock_ds.records.return_value = records
        mock_ai.is_configured.return_value = True

        def fake_analyze(text):
            return _ai_result(
                rating=5 if text == "first" else 1,
                sentiment="positive" if text == "first" else "negative",
            )
        mock_ai.analyze_review.side_effect = fake_analyze
        metrics = svc.run()
    cache = svc._cache()
    assert cache["R1"]["predicted_rating"] == 5
    assert cache["R2"]["predicted_rating"] == 1
    assert metrics.rating_accuracy == 1.0
    assert metrics.confusion_matrix[0][0] == 1
    assert metrics.confusion_matrix[4][4] == 1


def test_empty_cache_metrics_is_none(tmp_path):
    svc = _service(tmp_path)
    assert svc.metrics(source="benchmark") is None
    with patch(
        "services.catalog.catalog_service.canonical_catalog"
    ) as mock_cat:
        mock_cat.is_configured.return_value = True
        mock_cat.get_dataset_version.return_value = "v1"
        assert svc.metrics(source="canonical") is None
