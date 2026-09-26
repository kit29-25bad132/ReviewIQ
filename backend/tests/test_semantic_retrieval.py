"""V2-P2 tests: indexing + semantic retrieval integration (offline).

review -> validate -> preprocess -> dedupe -> mocked embedding -> in-memory
vector repository -> semantic search result. No provider/DB required.
"""

import pytest

from services.embeddings.contracts import EmbeddingResponse, EmbeddingTaskType
from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.embeddings.registry import EmbeddingModelSpec
from services.embeddings.service import EmbeddingService
from services.retrieval.contracts import ValidationOutcome
from services.retrieval.indexing_service import ReviewIndexingService
from services.retrieval.search_service import SemanticSearchService
from services.retrieval.vector_repository import ReviewSearchFilters
from tests.retrieval_fakes import FakeEmbeddingProvider, InMemoryVectorRepository

DIMENSION = 16


def _embedding_service(provider, batch_size=100):
    return EmbeddingService(
        provider,
        spec=EmbeddingModelSpec(
            provider="fake", model="fake-embed", dimension=DIMENSION,
            max_batch_size=batch_size,
        ),
    )


def _stack(batch_size=100, script=None):
    provider = FakeEmbeddingProvider(dimension=DIMENSION, script=script)
    repository = InMemoryVectorRepository()
    embedding = _embedding_service(provider, batch_size=batch_size)
    indexer = ReviewIndexingService(embedding, repository, batch_size=batch_size)
    search = SemanticSearchService(embedding, repository)
    return provider, repository, indexer, search


REVIEWS = [
    {"review_id": "r1", "product_id": "p1", "review_text": "The battery drains quickly and dies by noon.", "rating": 1},
    {"review_id": "r2", "product_id": "p1", "review_text": "Battery life is excellent and lasts all day.", "rating": 5},
    {"review_id": "r3", "product_id": "p1", "review_text": "The camera takes blurry photos at night.", "rating": 2},
]


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def test_index_reviews_embeds_and_stores():
    provider, repository, indexer, _ = _stack()
    report = indexer.index(REVIEWS)
    assert report.accepted == 3
    assert report.invalid == 0
    assert report.duplicates == 0
    assert report.indexed == 3
    assert repository.count() == 3
    assert provider.calls[0].task_type is EmbeddingTaskType.RETRIEVAL_DOCUMENT


def test_index_reports_duplicates_without_reembedding():
    provider, repository, indexer, _ = _stack()
    records = [
        {"review_id": "r1", "product_id": "p1", "review_text": "Same review text here."},
        {"review_id": "r2", "product_id": "p1", "review_text": "  Same   review text here.  "},
    ]
    report = indexer.index(records)
    assert report.accepted == 2
    assert report.duplicates == 1
    assert report.indexed == 1
    assert repository.count() == 1
    assert sum(len(call.texts) for call in provider.calls) == 1


def test_index_reports_invalid_records():
    _, _, indexer, _ = _stack()
    report = indexer.index(
        [
            {"review_id": "ok", "product_id": "p1", "review_text": "valid text"},
            {"review_id": "missing", "product_id": "p1"},
            {"review_id": "empty", "product_id": "p1", "review_text": "   "},
        ]
    )
    assert report.invalid == 2
    assert report.indexed == 1
    assert [r.review_id for r in report.rejected] == ["missing", "empty"]
    assert report.rejected[0].outcome is ValidationOutcome.INVALID_MISSING_TEXT


def test_index_skips_already_indexed_reviews():
    provider, _, indexer, _ = _stack()
    indexer.index(REVIEWS)
    calls_after_first = len(provider.calls)
    report = indexer.index(REVIEWS)
    assert report.indexed == 0
    assert report.already_indexed == 3
    assert len(provider.calls) == calls_after_first  # no redundant embedding work


def test_index_reports_partial_batch_failure():
    failure = EmbeddingResponse.failure(
        provider="fake",
        model="fake-embed",
        error_type=EmbeddingErrorType.RATE_LIMIT,
        error_message="429 quota",
    )
    success = EmbeddingResponse(
        vectors=[[0.1] * DIMENSION, [0.2] * DIMENSION],
        provider="fake",
        model="fake-embed",
        dimension=DIMENSION,
        success=True,
    )
    _, repository, indexer, _ = _stack(batch_size=2, script=[success, failure])
    records = [
        {"review_id": "r1", "product_id": "p1", "review_text": "first unique text"},
        {"review_id": "r2", "product_id": "p1", "review_text": "second unique text"},
        {"review_id": "r3", "product_id": "p1", "review_text": "third unique text"},
        {"review_id": "r4", "product_id": "p1", "review_text": "fourth unique text"},
    ]
    report = indexer.index(records)
    assert report.indexed == 2
    assert report.failed == 2
    assert report.failed_review_ids == ("r3", "r4")
    assert report.metadata["last_error_type"] == "rate_limit"


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------

def test_semantic_search_returns_most_similar_review():
    _, _, indexer, search = _stack()
    indexer.index(REVIEWS)
    outcome = search.search("battery drains quickly", top_k=5)
    assert outcome.results
    assert outcome.results[0].review_text.startswith("The battery drains quickly")
    assert outcome.embedding_dimension == DIMENSION
    # Results are ordered by descending similarity.
    similarities = [r.similarity for r in outcome.results]
    assert similarities == sorted(similarities, reverse=True)


def test_semantic_search_uses_query_task_type():
    provider, _, indexer, search = _stack()
    indexer.index(REVIEWS)
    search.search("battery", top_k=1)
    assert provider.calls[-1].task_type is EmbeddingTaskType.RETRIEVAL_QUERY


def test_semantic_search_respects_top_k():
    _, _, indexer, search = _stack()
    indexer.index(REVIEWS)
    assert len(search.search("battery", top_k=1).results) == 1
    assert len(search.search("battery", top_k=2).results) == 2


def test_semantic_search_threshold_filters_all():
    _, _, indexer, search = _stack()
    indexer.index(REVIEWS)
    assert search.search("battery", top_k=5, similarity_threshold=0.99).results == ()


def test_semantic_search_metadata_filter():
    _, _, indexer, search = _stack()
    indexer.index(REVIEWS + [{"review_id": "r4", "product_id": "p2", "review_text": "battery issue on other product"}])
    outcome = search.search(
        "battery", top_k=5, filters=ReviewSearchFilters(product_id="p2")
    )
    assert outcome.results
    assert all(r.product_id == "p2" for r in outcome.results)


def test_semantic_search_rating_filter():
    _, _, indexer, search = _stack()
    indexer.index(REVIEWS)
    outcome = search.search(
        "battery", top_k=5, filters=ReviewSearchFilters(min_rating=1, max_rating=1)
    )
    assert outcome.results
    assert all(r.rating == 1 for r in outcome.results)


def test_semantic_search_empty_when_repository_empty():
    _, _, _, search = _stack()
    assert search.search("anything", top_k=5).results == ()


def test_semantic_search_invalid_query_rejected():
    _, _, _, search = _stack()
    with pytest.raises(EmbeddingError) as excinfo:
        search.search("   ")
    assert excinfo.value.error_type is EmbeddingErrorType.INVALID_INPUT


def test_semantic_search_top_k_bounds():
    _, _, _, search = _stack()
    with pytest.raises(EmbeddingError):
        search.search("battery", top_k=0)
    with pytest.raises(EmbeddingError):
        search.search("battery", top_k=101)


def test_semantic_search_invalid_threshold_rejected():
    _, _, _, search = _stack()
    with pytest.raises(EmbeddingError) as excinfo:
        search.search("battery", similarity_threshold=2.0)
    assert excinfo.value.error_type is EmbeddingErrorType.INVALID_INPUT
