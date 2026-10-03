"""Tests for Data Quality Pipeline (Pandera, DuckDB, Deduplication, Trustworthiness, Quality Gate)."""

import csv
from pathlib import Path
import pytest
import pandas as pd

from services.quality.pandera_contracts import validate_dataframe
from services.quality.duckdb_profiler import duckdb_profiler
from services.quality.duplicate_detector import duplicate_detector
from services.quality.trustworthiness_checker import trustworthiness_checker
from services.quality.quality_gate import quality_gate_runner

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
CSV_PATH = ROOT_DIR / "product_reviews_dataset.csv"
if not CSV_PATH.exists():
    CSV_PATH = BASE_DIR / "data" / "product_reviews_dataset.csv"


def test_pandera_validation_passes_canonical_dataset():
    df = pd.read_csv(CSV_PATH)
    is_valid, err_msg, validated_df = validate_dataframe(df)
    assert is_valid is True, f"Pandera validation failed: {err_msg}"
    assert err_msg is None
    assert validated_df is not None


def test_pandera_validation_catches_invalid_ratings():
    bad_df = pd.DataFrame([
        {
            "review_id": "R9999",
            "product_id": "P01",
            "product_name": "Test",
            "brand": "Test",
            "category": "Smartphone",
            "rating": 6,  # Invalid rating > 5
            "review_text": "Good phone",
            "sentiment": "positive",
        }
    ])
    is_valid, err_msg, _ = validate_dataframe(bad_df)
    assert is_valid is False
    assert err_msg is not None


def test_duckdb_profiler():
    profile = duckdb_profiler.profile_csv(CSV_PATH)
    assert profile["counts"]["total_rows"] == 1500
    assert profile["counts"]["unique_products"] == 20
    assert profile["counts"]["unique_reviews"] == 1500
    assert len(profile["category_distribution"]) == 5
    assert len(profile["brand_distribution"]) == 11
    assert len(profile["rating_distribution"]) == 5


def test_duplicate_detector():
    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))
    dup_report = duplicate_detector.analyze(reader)
    assert dup_report["exact_duplicates"]["count"] == 0
    assert dup_report["exact_duplicates"]["percentage"] == 0.0
    assert dup_report["normalized_duplicates"]["count"] == 0
    assert dup_report["near_duplicates"]["count"] == 0
    assert dup_report["template_repetitions"]["count"] == 0


def test_trustworthiness_checker():
    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))
    valid_pids = {row["product_id"].strip() for row in reader}
    t_report = trustworthiness_checker.check(reader, valid_pids)
    assert t_report["trustworthiness_score"] == 100.0
    assert t_report["orphan_reviews_count"] == 0
    assert t_report["provenance_coverage_pct"] == 100.0


def test_quality_gate_runner():
    passed, report = quality_gate_runner.evaluate_csv(CSV_PATH)
    assert passed is True
    assert report.status == "PASS"
    assert report.total_rows == 1500
    assert report.total_products == 20
    assert report.trustworthiness_score == 100.0
    assert report.exact_duplicate_count == 0
    assert report.orphan_reviews_count == 0
