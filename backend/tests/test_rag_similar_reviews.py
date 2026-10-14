"""Phase 7D focused tests for services/rag/similar_reviews.py (hermetic)."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.embeddings.errors import EmbeddingError
from services.retrieval.vector_repository import ReviewSearchResult
from services.rag import similar_reviews as sr


def _result(review_id, text, similarity, product_id="P12", rating=4):
    return ReviewSearchResult(
        review_id=review_id,
        review_text=text,
        normalized_text=text.lower(),
        similarity=similarity,
        distance=1.0 - similarity,
        embedding_model="gemini-embedding-001",
        product_id=product_id,
        rating=rating,
        source="canonical",
    )


class _FakeSearch:
    """Scripted SemanticSearchService double: records calls, pops outcomes."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = []

    def search(self, query_text, *, top_k=None, similarity_threshold=None, filters=None):
        self.calls.append(
            {"query": query_text, "top_k": top_k, "threshold": similarity_threshold,
             "filters": filters}
        )
        results = self._outcomes.pop(0) if self._outcomes else ()
        return SimpleNamespace(results=tuple(results))


def _with_fake(fake):
    return patch.object(sr, "_search", fake)


def test_maps_repository_results_to_retrieved_review():
    one = [
        _result("R00669", "the battery life is okay", 0.7462, rating=4),
    ]
    # 1 result < 3 triggers the legitimate 0.65 -> 0.50 retry; both passes
    # return the same row so the mapping assertions stay focused.
    fake = _FakeSearch([one, one])
    with _with_fake(fake):
        out = sr.retrieve_similar_reviews("battery life performance", "P12")
    assert len(out) == 1
    item = out[0]
    assert item.review_id == "R00669"
    assert item.source_review_id == "R00669"
    assert item.similarity_score == pytest.approx(0.7462)
    assert item.product_id == "P12"
    assert item.rating == 4
    assert item.source == "canonical"
    call = fake.calls[0]
    assert call["filters"].product_id == "P12"
    assert call["filters"].source == "canonical"
    assert call["threshold"] == pytest.approx(0.65)
    assert call["top_k"] == 10


def test_fallback_retries_once_at_0_50_when_fewer_than_three():
    fake = _FakeSearch([
        [_result("R1", "battery is fine", 0.68)],
        [
            _result("R1", "battery is fine", 0.68),
            _result("R2", "great battery backup for the price", 0.55),
            _result("R3", "charge lasts two days", 0.52),
        ],
    ])
    with _with_fake(fake):
        out = sr.retrieve_similar_reviews("battery", "P12")
    assert [c["threshold"] for c in fake.calls] == [0.65, 0.5]
    assert len(out) == 3


def test_no_fallback_when_first_pass_has_enough_results():
    fake = _FakeSearch([[
        _result("R1", "alpha battery text one", 0.8),
        _result("R2", "beta performance text two", 0.75),
        _result("R3", "gamma charge text three", 0.71),
    ]])
    with _with_fake(fake):
        out = sr.retrieve_similar_reviews("battery", "P12")
    assert len(fake.calls) == 1
    assert fake.calls[0]["threshold"] == pytest.approx(0.65)
    assert len(out) == 3


def test_no_fallback_when_threshold_already_at_or_below_0_50():
    fake = _FakeSearch([[_result("R1", "battery alone", 0.51)]])
    with _with_fake(fake):
        out = sr.retrieve_similar_reviews("battery", "P12", min_similarity=0.5)
    assert len(fake.calls) == 1
    assert fake.calls[0]["threshold"] == pytest.approx(0.5)
    assert len(out) == 1


def test_empty_retrieval_returns_empty_list_never_fabricates():
    fake = _FakeSearch([[]])
    with _with_fake(fake):
        out = sr.retrieve_similar_reviews("battery", "P12")
    assert out == []


def test_dedup_keeps_higher_similarity_and_drops_later_duplicate():
    fake = _FakeSearch([[
        _result("R1", "the battery life is okay, nothing special at all", 0.74),
        _result("R2", "the battery life is okay, nothing special at all!!", 0.71),
        _result("R3", "completely different topic about the keyboard", 0.70),
    ]])
    with _with_fake(fake):
        out = sr.retrieve_similar_reviews("battery", "P12")
    ids = [r.review_id for r in out]
    assert ids == ["R1", "R3"]


def test_text_overlap_containment_semantics():
    assert sr._text_overlap("battery is great", "battery is great") == 1.0
    # shorter fully contained in longer -> 1.0 (> 0.95 => duplicate)
    assert sr._text_overlap("battery great", "battery great and cheap too") == 1.0
    # half shared -> 0.5 (not a duplicate)
    assert sr._text_overlap("battery great", "battery awful") == pytest.approx(0.5)
    assert sr._text_overlap("", "anything") == 0.0


def test_invalid_inputs_raise_embedding_error():
    with pytest.raises(EmbeddingError):
        sr.retrieve_similar_reviews("", "P12")
    with pytest.raises(EmbeddingError):
        sr.retrieve_similar_reviews("battery", "")
    with pytest.raises(EmbeddingError):
        sr.retrieve_similar_reviews("battery", "P12", top_k=0)
    with pytest.raises(EmbeddingError):
        sr.retrieve_similar_reviews("battery", "P12", top_k=21)
    with pytest.raises(EmbeddingError):
        sr.retrieve_similar_reviews("battery", "P12", min_similarity=2.0)


def test_detailed_surfaces_fallback_flag_and_delegate_matches():
    fake = _FakeSearch([
        [_result("R1", "battery is fine", 0.68)],
        [
            _result("R1", "battery is fine", 0.68),
            _result("R2", "great battery backup for the price", 0.55),
            _result("R3", "charge lasts two days", 0.52),
        ],
    ])
    with _with_fake(fake):
        outcome = sr.retrieve_similar_reviews_detailed("battery", "P12")
    assert outcome.fallback_triggered is True
    assert [r.review_id for r in outcome.reviews] == ["R1", "R2", "R3"]

    three = [
        _result("R1", "alpha battery text one", 0.8),
        _result("R2", "beta performance text two", 0.75),
        _result("R3", "gamma charge text three", 0.71),
    ]
    fake2 = _FakeSearch([three, three])
    with _with_fake(fake2):
        delegate = sr.retrieve_similar_reviews("battery", "P12")
        outcome2 = sr.retrieve_similar_reviews_detailed("battery", "P12")
    assert outcome2.fallback_triggered is False
    assert [r.review_id for r in delegate] == [r.review_id for r in outcome2.reviews]
