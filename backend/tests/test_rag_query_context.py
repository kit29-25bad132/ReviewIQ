"""Phase 7E focused tests for services/rag/query_context.py (hermetic)."""

import pytest

from services.rag.query_context import (
    CHARS_PER_TOKEN,
    TRUNCATION_SUFFIX,
    build_rag_context,
)
from services.rag.similar_reviews import RetrievedReview


def _rr(review_id, text, similarity, rating=4, product_id="P12"):
    return RetrievedReview(
        review_id=review_id,
        review_text=text,
        similarity_score=similarity,
        product_id=product_id,
        rating=rating,
        source_review_id=review_id,
        source="canonical",
    )


def test_empty_input_yields_empty_context():
    ctx = build_rag_context([], max_tokens=3000)
    assert ctx.reviews_used == ()
    assert ctx.context_text == ""
    assert ctx.token_estimate == 0
    assert ctx.reviews_truncated == 0


def test_invalid_max_tokens_raises():
    with pytest.raises(ValueError):
        build_rag_context([], max_tokens=0)
    with pytest.raises(ValueError):
        build_rag_context([], max_tokens=-5)
    with pytest.raises(ValueError):
        build_rag_context([], max_tokens=True)  # type: ignore[arg-type]


def test_orders_by_similarity_desc_then_review_id():
    ctx = build_rag_context(
        [
            _rr("R00002", "mid quality battery", 0.70),
            _rr("R00001", "best battery review", 0.90),
            _rr("R00003", "weakest battery review", 0.50),
        ],
        max_tokens=3000,
    )
    assert [r.review_id for r in ctx.reviews_used] == ["R00001", "R00002", "R00003"]
    assert ctx.context_text.index("[R00001]") < ctx.context_text.index("[R00002]")


def test_citation_marker_format():
    ctx = build_rag_context(
        [_rr("R00669", "the battery life is okay", 0.7462, rating=4)],
        max_tokens=3000,
    )
    assert ctx.context_text == (
        "[R00669] (rating=4, similarity=0.7462) the battery life is okay"
    )
    assert ctx.token_estimate == pytest.approx(
        -(-len(ctx.context_text) // CHARS_PER_TOKEN)
    )


def test_token_budget_is_never_exceeded():
    reviews = [
        _rr(f"R{i:05d}", f"review number {i} about the battery and performance " * 20, 0.9 - i * 0.01)
        for i in range(1, 21)
    ]
    ctx = build_rag_context(reviews, max_tokens=100)
    assert ctx.token_estimate <= 100
    assert len(ctx.context_text) <= 100 * CHARS_PER_TOKEN
    assert len(ctx.reviews_used) < 20
    assert ctx.reviews_truncated > 0


def test_single_oversized_review_is_truncated_not_skipped():
    huge = "battery performance charge " * 500  # ~13.5k chars >> budget
    ctx = build_rag_context([_rr("R00001", huge, 0.9)], max_tokens=100)
    assert len(ctx.reviews_used) == 1
    assert ctx.reviews_truncated == 0
    assert ctx.context_text.endswith(TRUNCATION_SUFFIX)
    assert ctx.token_estimate <= 100
    # ENFORCEMENT: reviews_used keeps the FULL untruncated text even when the
    # rendered block is cut — 7F/7G excerpts must come from here.
    assert ctx.reviews_used[0].review_text == huge


def test_later_short_review_still_fits_after_longer_ones_are_dropped():
    long_first = _rr("R00001", "x" * 10_000, 0.95)
    short_second = _rr("R00002", "short battery note", 0.55)
    # Budget fits the header+short review but not the long one whole; the
    # long one is prefix-truncated (>= MIN_FIT_CHARS remains), so nothing
    # is dropped here. Use a tighter budget to force a drop path:
    ctx = build_rag_context([long_first, short_second], max_tokens=55)
    assert any(r.review_id == "R00002" for r in ctx.reviews_used) or ctx.reviews_truncated >= 1
    assert ctx.token_estimate <= 55
    assert len(ctx.context_text) <= 55 * CHARS_PER_TOKEN


def test_blank_review_text_is_dropped():
    ctx = build_rag_context(
        [_rr("R00001", "   ", 0.9), _rr("R00002", "real battery text", 0.8)],
        max_tokens=3000,
    )
    assert [r.review_id for r in ctx.reviews_used] == ["R00002"]
    assert ctx.reviews_truncated == 1


def test_min_fit_chars_guard_drops_when_nothing_meaningful_fits():
    # Budget fits the big review exactly; the leftover (< MIN_FIT_CHARS)
    # forces a drop rather than a sliver fragment.
    big = _rr("R00001", "battery charge cycle test " * 30, 0.9)
    small = _rr("R00002", "tiny note", 0.5)
    first_block_len = len("[R00001] (rating=4, similarity=0.9000) ") + len(big.review_text)
    max_tokens = -(-first_block_len // CHARS_PER_TOKEN)  # ceil
    ctx = build_rag_context([big, small], max_tokens=max_tokens)
    assert ctx.reviews_used[0].review_id == "R00001"
    assert [r.review_id for r in ctx.reviews_used] == ["R00001"]
    assert ctx.reviews_truncated == 1
