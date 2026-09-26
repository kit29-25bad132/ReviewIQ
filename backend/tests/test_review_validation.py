"""V2-P2 tests: review validation outcomes (offline)."""

from services.retrieval.contracts import ValidationOutcome
from services.retrieval.review_validation import validate_review, validate_reviews


def _valid_record(**overrides):
    record = {
        "review_id": "r1",
        "product_id": "p1",
        "review_text": "The battery lasts all day.",
        "rating": 5,
    }
    record.update(overrides)
    return record


def test_valid_review_accepted():
    validated, rejected = validate_review(_valid_record())
    assert rejected is None
    assert validated.review_id == "r1"
    assert validated.product_id == "p1"
    assert validated.review_text == "The battery lasts all day."
    assert validated.rating == 5


def test_review_text_is_stripped():
    validated, _ = validate_review(_valid_record(review_text="  spaced out  "))
    assert validated.review_text == "spaced out"


def test_dataset_style_aliases_supported():
    # Mirrors services/dataset_service.DatasetReview field names.
    validated, rejected = validate_review(
        {"id": "d1", "asin": "A123", "review_text": "ok text", "actual_rating": 3}
    )
    assert rejected is None
    assert validated.review_id == "d1"
    assert validated.product_id == "A123"
    assert validated.rating == 3


def test_object_attribute_input_supported():
    class Row:
        review_id = "obj1"
        product_id = "p9"
        review_text = "great camera"
        rating = 4

    validated, rejected = validate_review(Row())
    assert rejected is None
    assert validated.review_id == "obj1"
    assert validated.rating == 4


def test_missing_review_text_rejected():
    _, rejected = validate_review({"review_id": "x", "product_id": "p"})
    assert rejected.outcome is ValidationOutcome.INVALID_MISSING_TEXT


def test_null_review_text_rejected():
    _, rejected = validate_review(_valid_record(review_text=None))
    assert rejected.outcome is ValidationOutcome.INVALID_MISSING_TEXT


def test_empty_review_text_rejected():
    _, rejected = validate_review(_valid_record(review_text=""))
    assert rejected.outcome is ValidationOutcome.INVALID_EMPTY_TEXT


def test_whitespace_only_review_rejected():
    _, rejected = validate_review(_valid_record(review_text="   \n\t  "))
    assert rejected.outcome is ValidationOutcome.INVALID_EMPTY_TEXT


def test_overlong_review_rejected():
    _, rejected = validate_review(_valid_record(review_text="x" * 20_001))
    assert rejected.outcome is ValidationOutcome.INVALID_TEXT_TOO_LONG


def test_null_record_rejected_as_malformed():
    _, rejected = validate_review(None)
    assert rejected.outcome is ValidationOutcome.INVALID_MALFORMED


def test_non_string_review_text_is_malformed():
    _, rejected = validate_review(_valid_record(review_text=12345))
    assert rejected.outcome is ValidationOutcome.INVALID_MALFORMED


def test_container_identifier_is_malformed():
    _, rejected = validate_review(_valid_record(review_id=["not", "scalar"]))
    assert rejected.outcome is ValidationOutcome.INVALID_MALFORMED


def test_out_of_range_rating_is_invalid_metadata():
    for bad in (0, 6, -1):
        _, rejected = validate_review(_valid_record(rating=bad))
        assert rejected.outcome is ValidationOutcome.INVALID_METADATA


def test_non_numeric_rating_is_invalid_metadata():
    _, rejected = validate_review(_valid_record(rating="not-a-number"))
    assert rejected.outcome is ValidationOutcome.INVALID_METADATA


def test_invalid_review_date_is_invalid_metadata():
    _, rejected = validate_review(_valid_record(review_date="not-a-date"))
    assert rejected.outcome is ValidationOutcome.INVALID_METADATA


def test_valid_review_date_parsed():
    validated, _ = validate_review(_valid_record(review_date="2024-01-02T03:04:05"))
    assert validated.review_date is not None
    assert validated.review_date.year == 2024


def test_numeric_string_rating_coerced():
    validated, _ = validate_review(_valid_record(rating="4"))
    assert validated.rating == 4


def test_validate_reviews_reports_counts_and_preserves_order():
    records = [
        _valid_record(review_id="a"),
        {"review_id": "b"},
        _valid_record(review_id="c", review_text="   "),
        _valid_record(review_id="d"),
    ]
    report = validate_reviews(records)
    assert [r.review_id for r in report.accepted] == ["a", "d"]
    assert [r.review_id for r in report.rejected] == ["b", "c"]
    assert report.rejected[0].outcome is ValidationOutcome.INVALID_MISSING_TEXT
    assert report.rejected[1].outcome is ValidationOutcome.INVALID_EMPTY_TEXT
