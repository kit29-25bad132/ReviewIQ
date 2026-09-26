"""V2-P2 tests: deterministic review preprocessing (offline)."""

import pytest

from services.retrieval.preprocessing import preprocess_review_text, preprocess_reviews


def test_whitespace_normalization_example():
    raw = "  Battery is AMAZING!!! \n\n  but heats up. "
    assert preprocess_review_text(raw) == "Battery is AMAZING!!! but heats up."


def test_preserves_punctuation_and_case():
    raw = "Not bad... but WHY so expensive?!"
    assert preprocess_review_text(raw) == "Not bad... but WHY so expensive?!"


def test_control_characters_removed_but_word_boundaries_kept():
    raw = "good\x00quality\x07product"
    assert preprocess_review_text(raw) == "good quality product"


def test_zero_width_characters_removed():
    raw = "bat\u200btery\u200d life\ufeff"
    assert preprocess_review_text(raw) == "battery life"


def test_tabs_become_single_space():
    raw = "one\ttwo\t\tthree"
    assert preprocess_review_text(raw) == "one two three"


def test_nfkc_normalization():
    # Full-width characters normalize to ASCII; wording is unchanged.
    assert preprocess_review_text("Ｇｒｅａｔ　ｐｈｏｎｅ") == "Great phone"


def test_semantic_wording_not_altered():
    raw = "I did not dislike the phone, but the battery is not great."
    assert preprocess_review_text(raw) == raw


def test_output_is_deterministic_and_idempotent():
    raw = "  Mixed   feelings... \n but  overall good. "
    first = preprocess_review_text(raw)
    second = preprocess_review_text(raw)
    assert first == second
    assert preprocess_review_text(first) == first


def test_batch_preserves_order():
    texts = ["  a  ", "b\n\nb", " c "]
    assert preprocess_reviews(texts) == ["a", "b b", "c"]


def test_non_string_raises_type_error():
    with pytest.raises(TypeError):
        preprocess_review_text(None)
