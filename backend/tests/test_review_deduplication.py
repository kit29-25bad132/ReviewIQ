"""V2-P2 tests: deterministic review deduplication (offline)."""

from services.retrieval.contracts import ValidatedReview
from services.retrieval.deduplication import (
    canonicalize_for_fingerprint,
    dedupe_prepared,
    prepare_review,
    review_fingerprint,
)
from services.retrieval.review_validation import validate_review


def _prepared(text, product_id="p1", review_id=None):
    review = ValidatedReview(
        review_id=review_id, product_id=product_id, review_text=text
    )
    return prepare_review(review)


def _fingerprint_of(text, product_id="p1"):
    return review_fingerprint(product_id, canonicalize_for_fingerprint(text))


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------

def test_fingerprint_is_deterministic():
    assert _fingerprint_of("The battery lasts all day.") == (
        _fingerprint_of("The battery lasts all day.")
    )


def test_fingerprint_ignores_whitespace_differences():
    assert _fingerprint_of("battery lasts  all day") == _fingerprint_of(
        "  battery lasts all day  "
    )


def test_fingerprint_ignores_case_differences():
    assert _fingerprint_of("Battery LASTS all day") == _fingerprint_of(
        "battery lasts all day"
    )


def test_fingerprint_differs_by_product():
    assert _fingerprint_of("great phone", product_id="p1") != _fingerprint_of(
        "great phone", product_id="p2"
    )


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_exact_duplicates_collapsed():
    report = dedupe_prepared(
        [_prepared("Great battery life."), _prepared("Great battery life.")]
    )
    assert len(report.accepted) == 1
    assert len(report.duplicates) == 1


def test_whitespace_normalized_duplicate_collapsed():
    report = dedupe_prepared(
        [_prepared("Great battery life."), _prepared("  Great   battery life.  ")]
    )
    assert len(report.accepted) == 1
    assert len(report.duplicates) == 1


def test_same_text_different_products_are_both_kept():
    report = dedupe_prepared(
        [
            _prepared("Great battery life.", product_id="p1"),
            _prepared("Great battery life.", product_id="p2"),
        ]
    )
    assert len(report.accepted) == 2
    assert report.duplicates == ()


def test_first_occurrence_wins():
    first = _prepared("same text", review_id="first")
    second = _prepared("same text", review_id="second")
    report = dedupe_prepared([first, second])
    assert report.accepted[0].review_id == "first"
    assert report.duplicates[0].review_id == "second"


def test_missing_review_id_falls_back_to_fingerprint():
    prepared = _prepared("unique review text here")
    assert prepared.review.review_id is None
    assert prepared.review_id == prepared.fingerprint


def test_prepare_review_normalizes_text():
    validated, _ = validate_review(
        {"product_id": "p1", "review_text": "  battery   is  fine. "}
    )
    prepared = prepare_review(validated)
    assert prepared.normalized_text == "battery is fine."
