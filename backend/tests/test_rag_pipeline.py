"""V2-P3 tests: RAG config, retrieval, context building, prompting (offline).

No network, no database, no provider SDK: retrieval runs over the P2 search
service with the shared in-memory fakes (tests/retrieval_fakes.py), and the
context/prompt layer is pure.
"""

import pytest

from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.embeddings.registry import EmbeddingModelSpec
from services.embeddings.service import EmbeddingService
from services.rag.config import DEFAULT_RAG_ENABLED, RAGConfig
from services.rag.context_builder import (
    TRUNCATION_MARKER,
    build_rag_context,
    render_context_block,
)
from services.rag.prompting import (
    BASE_PROMPT,
    CONTEXT_HEADER,
    CONTEXT_SYSTEM_RULES,
    ORIGINAL_REVIEW_HEADER,
    build_analysis_prompt,
)
from services.rag.retrieval import RagRetrievalService, RagRetrievalStatus
from services.retrieval.indexing_service import ReviewIndexingService
from services.retrieval.search_service import SemanticSearchService
from services.retrieval.vector_repository import ReviewSearchResult
from tests.retrieval_fakes import FakeEmbeddingProvider, InMemoryVectorRepository

DIMENSION = 16

RAG_ENV_VARS = (
    "RAG_ENABLED",
    "RAG_TOP_K",
    "RAG_SIMILARITY_THRESHOLD",
    "RAG_MAX_CONTEXT_REVIEWS",
    "RAG_MAX_CONTEXT_CHARS",
    "RAG_MAX_REVIEW_CHARS",
)


def _search_stack():
    provider = FakeEmbeddingProvider(dimension=DIMENSION)
    repository = InMemoryVectorRepository()
    embedding = EmbeddingService(
        provider,
        spec=EmbeddingModelSpec(
            provider="fake", model="fake-embed", dimension=DIMENSION,
            max_batch_size=100,
        ),
    )
    indexer = ReviewIndexingService(embedding, repository)
    search = SemanticSearchService(embedding, repository)
    return repository, indexer, search


def _result(review_id, text, similarity, **kwargs):
    distance = 1.0 - similarity if isinstance(similarity, (int, float)) else 1.0
    return ReviewSearchResult(
        review_id=review_id,
        review_text=text,
        normalized_text=text,
        similarity=similarity,
        distance=distance,
        embedding_model="fake-embed",
        **kwargs,
    )


REVIEWS = [
    {"review_id": "r1", "product_id": "p1", "review_text": "The battery drains quickly and dies by noon.", "rating": 1},
    {"review_id": "r2", "product_id": "p1", "review_text": "Battery life is excellent and lasts all day.", "rating": 5},
    {"review_id": "r3", "product_id": "p1", "review_text": "The camera takes blurry photos at night.", "rating": 2},
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_config_defaults_keep_rag_disabled():
    config = RAGConfig()
    assert DEFAULT_RAG_ENABLED is False
    assert config.enabled is False
    assert config.top_k == 5
    assert config.similarity_threshold == 0.35
    assert config.max_context_reviews == 5
    assert config.max_context_chars == 6000
    assert config.max_review_chars == 1000


def test_config_from_env_parses_values(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_TOP_K", "7")
    monkeypatch.setenv("RAG_SIMILARITY_THRESHOLD", "0.5")
    monkeypatch.setenv("RAG_MAX_CONTEXT_REVIEWS", "3")
    monkeypatch.setenv("RAG_MAX_CONTEXT_CHARS", "1500")
    monkeypatch.setenv("RAG_MAX_REVIEW_CHARS", "300")
    config = RAGConfig.from_env()
    assert config.enabled is True
    assert config.top_k == 7
    assert config.similarity_threshold == 0.5
    assert config.max_context_reviews == 3
    assert config.max_context_chars == 1500
    assert config.max_review_chars == 300


def test_config_from_env_defaults_when_unset(monkeypatch):
    for name in RAG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert RAGConfig.from_env() == RAGConfig()


def test_config_from_env_rejects_invalid_values(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "maybe")
    monkeypatch.setenv("RAG_TOP_K", "999")
    monkeypatch.setenv("RAG_SIMILARITY_THRESHOLD", "7")
    monkeypatch.setenv("RAG_MAX_CONTEXT_REVIEWS", "0")
    monkeypatch.setenv("RAG_MAX_CONTEXT_CHARS", "10")
    monkeypatch.setenv("RAG_MAX_REVIEW_CHARS", "999999")
    assert RAGConfig.from_env() == RAGConfig()


def test_config_from_env_accepts_off_flag(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "OFF")
    assert RAGConfig.from_env().enabled is False


# ---------------------------------------------------------------------------
# Retrieval stage
# ---------------------------------------------------------------------------

def test_retrieval_disabled_returns_empty_metadata_without_search():
    class _Exploding:
        def search(self, *args, **kwargs):
            raise AssertionError("search must not run when RAG is disabled")

    service = RagRetrievalService(RAGConfig(), search_service=_Exploding())
    result = service.retrieve("battery life")
    assert result.results == ()
    meta = result.metadata
    assert meta.enabled is False
    assert meta.status == RagRetrievalStatus.DISABLED.value
    assert meta.query == "battery life"
    assert meta.top_k == 5
    assert meta.similarity_threshold == 0.35
    assert meta.retrieved_count == 0
    assert meta.error_type is None


def test_retrieval_returns_metadata_and_deterministic_order():
    _, indexer, search = _search_stack()
    assert indexer.index(REVIEWS).indexed == 3
    config = RAGConfig(enabled=True, top_k=3, similarity_threshold=0.0)
    service = RagRetrievalService(config, search_service=search)

    result = service.retrieve("battery life excellent")
    meta = result.metadata
    assert meta.enabled is True
    assert meta.status == RagRetrievalStatus.OK.value
    assert meta.top_k == 3
    assert meta.similarity_threshold == 0.0
    assert meta.error_type is None
    assert meta.retrieved_count == len(result.results) >= 1

    keys = [(-r.similarity, r.review_id) for r in result.results]
    assert keys == sorted(keys)
    assert result == service.retrieve("battery life excellent")


def test_retrieval_respects_top_k_and_threshold():
    _, indexer, search = _search_stack()
    indexer.index(REVIEWS)

    one = RagRetrievalService(
        RAGConfig(enabled=True, top_k=1, similarity_threshold=0.0),
        search_service=search,
    ).retrieve("battery life")
    assert len(one.results) == 1

    strict = RagRetrievalService(
        RAGConfig(enabled=True, top_k=3, similarity_threshold=1.0),
        search_service=search,
    ).retrieve("battery life")
    assert strict.results == ()
    assert strict.metadata.status == RagRetrievalStatus.EMPTY.value
    assert strict.metadata.retrieved_count == 0


def test_retrieval_invalid_query_returns_invalid_status():
    _, _, search = _search_stack()
    service = RagRetrievalService(
        RAGConfig(enabled=True), search_service=search
    )
    result = service.retrieve("   ")
    assert result.results == ()
    assert result.metadata.status == RagRetrievalStatus.INVALID.value
    assert result.metadata.error_type == "invalid_input"


def test_retrieval_captures_normalized_embedding_failure():
    class _Failing:
        def search(self, *args, **kwargs):
            raise EmbeddingError(
                "missing key", EmbeddingErrorType.AUTHENTICATION
            )

    service = RagRetrievalService(
        RAGConfig(enabled=True), search_service=_Failing()
    )
    result = service.retrieve("query")
    assert result.results == ()
    assert result.metadata.status == RagRetrievalStatus.UNAVAILABLE.value
    assert result.metadata.error_type == "authentication"


def test_retrieval_never_raises_on_unexpected_failure():
    class _Exploding:
        def search(self, *args, **kwargs):
            raise RuntimeError("boom")

    service = RagRetrievalService(
        RAGConfig(enabled=True), search_service=_Exploding()
    )
    result = service.retrieve("query")
    assert result.results == ()
    assert result.metadata.status == RagRetrievalStatus.UNAVAILABLE.value
    assert result.metadata.error_type == "unknown"


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def test_context_builder_preserves_order_and_caps_review_count():
    results = [
        _result("r1", "text one", 0.9),
        _result("r2", "text two", 0.8),
        _result("r3", "text three", 0.7),
    ]
    ctx = build_rag_context(results, RAGConfig(enabled=True, max_context_reviews=2))
    assert [r.review_id for r in ctx.reviews] == ["r1", "r2"]
    assert ctx.skipped == 0
    assert ctx.is_empty is False
    assert ctx.char_count == len(ctx.block)
    assert "text three" not in ctx.block
    assert "[1] similarity=0.9000" in ctx.block
    assert "[2] similarity=0.8000" in ctx.block


def test_context_builder_skips_malformed_entries():
    results = [
        _result("good", "valid text", 0.8),
        _result("blank-text", "   ", 0.7),
        _result("nan-sim", "some text", float("nan")),
        _result("", "orphan text", 0.6),
        _result("no-sim", "other text", None),
    ]
    ctx = build_rag_context(results, RAGConfig(enabled=True))
    assert [r.review_id for r in ctx.reviews] == ["good"]
    assert ctx.skipped == 4
    assert "valid text" in ctx.block


def test_context_builder_omits_missing_metadata_fields():
    ctx = build_rag_context([_result("r1", "text", 0.5)], RAGConfig(enabled=True))
    assert "rating=" not in ctx.block
    assert "product_id=" not in ctx.block
    assert "source=" not in ctx.block
    assert "review_id=r1" in ctx.block
    assert "None" not in ctx.block


def test_context_builder_includes_metadata_when_present():
    ctx = build_rag_context(
        [_result("r1", "text", 0.5, rating=4, product_id="p9", source="live")],
        RAGConfig(enabled=True),
    )
    assert "rating=4" in ctx.block
    assert "product_id=p9" in ctx.block
    assert "source=live" in ctx.block


def test_context_builder_truncates_long_reviews():
    long_text = "word " * 500
    ctx = build_rag_context(
        [_result("r1", long_text, 0.9)],
        RAGConfig(enabled=True, max_review_chars=100),
    )
    review = ctx.reviews[0]
    assert review.truncated is True
    assert ctx.truncated is True
    assert review.text.endswith(TRUNCATION_MARKER)
    assert len(review.text) <= 100
    assert review.text in ctx.block


def test_context_builder_enforces_total_char_budget():
    results = [
        _result(f"r{i}", "some sentence " * 20, 0.9 - i * 0.01)
        for i in range(5)
    ]
    config = RAGConfig(enabled=True, max_context_chars=500, max_review_chars=400)
    ctx = build_rag_context(results, config)
    assert ctx.char_count <= 500
    assert 1 <= len(ctx.reviews) < 5


def test_context_builder_is_deterministic():
    results = [
        _result("r1", "text one", 0.9, rating=3),
        _result("r2", "text two", 0.8),
    ]
    config = RAGConfig(enabled=True)
    first = build_rag_context(results, config)
    second = build_rag_context(results, config)
    assert first == second


def test_context_builder_empty_results_render_empty():
    ctx = build_rag_context([], RAGConfig(enabled=True))
    assert ctx.is_empty is True
    assert ctx.block == ""
    assert ctx.char_count == 0
    assert ctx.skipped == 0
    assert render_context_block(ctx) == ""
    assert render_context_block(None) == ""


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------

REVIEW_TEXT = "The battery lasts all day and the display is bright."


def test_prompt_without_context_is_byte_identical_to_v1():
    base = "BASE SYSTEM INSTRUCTION"
    prompt, system = build_analysis_prompt(REVIEW_TEXT, None, base)
    assert prompt == (
        'Analyze this customer product review:\n\n"""\n'
        f'{REVIEW_TEXT}\n"""'
    )
    assert prompt == BASE_PROMPT.format(text=REVIEW_TEXT)
    assert system == base

    empty = build_rag_context([], RAGConfig(enabled=True))
    prompt2, system2 = build_analysis_prompt(REVIEW_TEXT, empty, base)
    assert prompt2 == prompt
    assert system2 == base


def test_prompt_with_context_contains_original_and_context_sections():
    ctx = build_rag_context(
        [_result("r1", "Charges fast via USB-C.", 0.8, rating=5, source="live")],
        RAGConfig(enabled=True),
    )
    base = "BASE SYSTEM INSTRUCTION"
    prompt, system = build_analysis_prompt(REVIEW_TEXT, ctx, base)

    assert prompt.startswith("Analyze this customer product review.")
    original_at = prompt.index(ORIGINAL_REVIEW_HEADER)
    context_at = prompt.index(CONTEXT_HEADER)
    assert original_at < context_at
    assert f'"""\n{REVIEW_TEXT}\n"""' in prompt
    assert "Charges fast via USB-C." in prompt
    assert "review_id=r1" in prompt
    assert system == base + CONTEXT_SYSTEM_RULES


def test_context_rules_confine_evidence_to_the_original_review():
    ctx = build_rag_context(
        [_result("r1", "Context-only detail.", 0.8)],
        RAGConfig(enabled=True),
    )
    _, system = build_analysis_prompt(REVIEW_TEXT, ctx, "BASE")
    assert "ONLY source of truth" in system
    assert "must be text present in the original customer review" in system
    assert "Never quote, paraphrase" in system
    assert "background context" in system.lower()
