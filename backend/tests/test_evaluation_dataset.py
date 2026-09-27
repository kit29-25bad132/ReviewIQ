"""V2-P10 tests: fixed offline evaluation dataset integrity.

Reads the committed backend/data/evaluation_set.json (works from a fresh
checkout without the gitignored amazon_review.csv). Verifies schema, labels,
sentiment-rule conformance, absence of invented labels, and deterministic
ordering. Offline, read-only, no network.
"""

import json
from pathlib import Path

from services.dataset_service import dataset_service

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "evaluation_set.json"

ALLOWED_RECORD_FIELDS = {"id", "review_text", "expected_rating", "expected_sentiment"}
FORBIDDEN_LABEL_KEYS = {
    "aspect",
    "aspects",
    "expected_aspects",
    "evidence",
    "expected_evidence",
    "pros",
    "cons",
    "expected_pros",
    "expected_cons",
    "summary",
    "expected_summary",
    "expected_rating_source",
}


def _load() -> dict:
    assert DATASET_PATH.is_file(), "evaluation_set.json must be committed"
    with DATASET_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_dataset_file_exists_and_is_valid_json():
    data = _load()
    assert isinstance(data, dict)


def test_schema_version_and_metadata_exist():
    data = _load()
    assert data["schema_version"] == "1.0"
    assert data["source"] == "amazon_review.csv"
    assert data["label_methodology"]
    assert data["selection"]


def test_records_non_empty_and_within_target_range():
    records = _load()["records"]
    assert 30 <= len(records) <= 50


def test_every_record_has_exactly_the_expected_fields():
    for record in _load()["records"]:
        assert set(record) == ALLOWED_RECORD_FIELDS


def test_ids_are_unique_and_non_empty():
    ids = [record["id"] for record in _load()["records"]]
    assert all(isinstance(i, str) and i for i in ids)
    assert len(set(ids)) == len(ids)


def test_review_text_is_non_empty_string():
    for record in _load()["records"]:
        text = record["review_text"]
        assert isinstance(text, str)
        assert text.strip()
        assert text == " ".join(text.split())


def test_expected_rating_is_integer_1_to_5():
    for record in _load()["records"]:
        rating = record["expected_rating"]
        assert isinstance(rating, int) and not isinstance(rating, bool)
        assert 1 <= rating <= 5


def test_expected_sentiment_is_supported_value():
    allowed = {"positive", "neutral", "negative"}
    for record in _load()["records"]:
        assert record["expected_sentiment"] in allowed


def test_expected_sentiment_matches_rating_sentiment_rule():
    for record in _load()["records"]:
        expected = dataset_service.sentiment_from_rating(record["expected_rating"])
        assert record["expected_sentiment"] == expected


def test_no_invented_aspect_or_evidence_labels_present():
    data = _load()
    for key in FORBIDDEN_LABEL_KEYS:
        assert key not in data, key
    for record in data["records"]:
        for key in FORBIDDEN_LABEL_KEYS:
            assert key not in record, key


def test_record_count_field_matches_records():
    data = _load()
    assert data["record_count"] == len(data["records"])


def test_ordering_is_deterministic_rating_ascending_then_id():
    records = _load()["records"]
    keys = [(r["expected_rating"], r["id"]) for r in records]
    assert keys == sorted(keys)


def test_all_rating_classes_are_represented():
    ratings = {record["expected_rating"] for record in _load()["records"]}
    assert ratings == {1, 2, 3, 4, 5}


def test_sentiment_classes_have_multiple_records():
    counts = {}
    for record in _load()["records"]:
        counts[record["expected_sentiment"]] = counts.get(record["expected_sentiment"], 0) + 1
    assert counts.get("positive", 0) >= 5
    assert counts.get("negative", 0) >= 5
    assert counts.get("neutral", 0) >= 5
