"""V2-P2 tests: embedding abstraction, service, and Gemini adapter (offline)."""

import sys

import pytest

from services.embeddings.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingTaskType,
)
from services.embeddings.errors import EmbeddingError, EmbeddingErrorType, classify_embedding_error
from services.embeddings.providers.gemini import GeminiEmbeddingProvider
from services.embeddings.registry import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingModelSpec,
    resolve_embedding_model_spec,
)
from services.embeddings.service import EmbeddingService
from tests.retrieval_fakes import (
    FakeContentEmbedding,
    FakeEmbedContentResponse,
    FakeEmbeddingProvider,
    install_fake_genai,
    hashing_vector,
)


def _spec(dimension=8, batch_size=2):
    return EmbeddingModelSpec(
        provider="fake", model="fake-embed", dimension=dimension, max_batch_size=batch_size
    )


def _service(dimension=8, batch_size=2, provider=None, preprocessor=None):
    provider = provider or FakeEmbeddingProvider(dimension=dimension)
    return EmbeddingService(
        provider,
        spec=_spec(dimension, batch_size),
        text_preprocessor=preprocessor,
    )


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

def test_provider_interface_embed_text_and_batch():
    provider = FakeEmbeddingProvider(dimension=8)
    single = provider.embed_text("battery life")
    assert single.success is True
    assert len(single.vectors) == 1

    batch = provider.embed_batch(["one", "two"])
    assert len(batch.vectors) == 2
    assert len(provider.calls) == 2


def test_provider_is_configured_flag():
    assert FakeEmbeddingProvider(configure=True).is_configured() is True
    assert FakeEmbeddingProvider(configure=False).is_configured() is False


# ---------------------------------------------------------------------------
# Embedding service
# ---------------------------------------------------------------------------

def test_embed_text_returns_validated_vector():
    service = _service(dimension=8)
    vector = service.embed_text("battery lasts all day")
    assert len(vector) == 8
    assert vector == hashing_vector("battery lasts all day", 8)


def test_embed_batch_preserves_order():
    service = _service(dimension=8, batch_size=10)
    vectors = service.embed_batch(["first text", "second text"])
    assert vectors[0] == hashing_vector("first text", 8)
    assert vectors[1] == hashing_vector("second text", 8)


def test_embed_batch_respects_batch_size():
    provider = FakeEmbeddingProvider(dimension=8)
    service = EmbeddingService(provider, spec=_spec(8, batch_size=2))
    service.embed_batch([f"text {i}" for i in range(5)])
    assert [len(call.texts) for call in provider.calls] == [2, 2, 1]


def test_embed_batch_empty_input_returns_empty():
    assert _service().embed_batch([]) == []


def test_empty_text_rejected():
    with pytest.raises(EmbeddingError) as excinfo:
        _service().embed_text("   ")
    assert excinfo.value.error_type is EmbeddingErrorType.INVALID_INPUT


def test_provider_failure_response_normalized():
    failure = EmbeddingResponse.failure(
        provider="fake",
        model="fake-embed",
        error_type=EmbeddingErrorType.RATE_LIMIT,
        error_message="429 quota",
    )
    provider = FakeEmbeddingProvider(dimension=8, script=[failure])
    with pytest.raises(EmbeddingError) as excinfo:
        _service(provider=provider).embed_text("hello")
    assert excinfo.value.error_type is EmbeddingErrorType.RATE_LIMIT


def test_provider_exception_normalized():
    provider = FakeEmbeddingProvider(dimension=8, script=[RuntimeError("429 quota exceeded")])
    with pytest.raises(EmbeddingError) as excinfo:
        _service(provider=provider).embed_text("hello")
    assert excinfo.value.error_type is EmbeddingErrorType.RATE_LIMIT


def test_dimension_mismatch_rejected():
    # Provider returns a 4-dim vector but the spec expects 8.
    response = EmbeddingResponse(
        vectors=[[0.1, 0.2, 0.3, 0.4]],
        provider="fake",
        model="fake-embed",
        dimension=4,
        success=True,
    )
    provider = FakeEmbeddingProvider(dimension=8, script=[response])
    service = EmbeddingService(provider, spec=_spec(dimension=8, batch_size=4))
    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_text("hello")
    assert excinfo.value.error_type is EmbeddingErrorType.DIMENSION_MISMATCH


def test_empty_vector_rejected():
    failure = EmbeddingResponse(
        vectors=[[], ], provider="fake", model="fake-embed", dimension=8, success=True
    )
    provider = FakeEmbeddingProvider(dimension=8, script=[failure])
    with pytest.raises(EmbeddingError) as excinfo:
        _service(provider=provider).embed_text("hello")
    assert excinfo.value.error_type is EmbeddingErrorType.EMPTY_RESPONSE


def test_vector_count_mismatch_rejected():
    response = EmbeddingResponse(
        vectors=[[0.1] * 8], provider="fake", model="fake-embed", dimension=8, success=True
    )
    provider = FakeEmbeddingProvider(dimension=8, script=[response])
    service = EmbeddingService(provider, spec=_spec(8, batch_size=4))
    with pytest.raises(EmbeddingError) as excinfo:
        service.embed_batch(["one", "two"])
    assert excinfo.value.error_type is EmbeddingErrorType.INVALID_RESPONSE


def test_injected_preprocessor_is_applied():
    provider = FakeEmbeddingProvider(dimension=8)
    service = EmbeddingService(
        provider, spec=_spec(8), text_preprocessor=lambda text: text.strip().upper()
    )
    service.embed_text("  hi  ")
    assert provider.calls[0].texts == ("HI",)


def test_service_exposes_provider_config():
    service = _service(dimension=8)
    assert service.model == "fake-embed"
    assert service.dimension == 8
    assert service.is_configured() is True


# ---------------------------------------------------------------------------
# Registry / configuration
# ---------------------------------------------------------------------------

def test_default_embedding_spec(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_DIMENSION", raising=False)
    spec = resolve_embedding_model_spec()
    assert spec.model == DEFAULT_EMBEDDING_MODEL
    assert spec.dimension == DEFAULT_EMBEDDING_DIMENSION


def test_embedding_spec_env_override(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-embed")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1536")
    spec = resolve_embedding_model_spec()
    assert spec.model == "custom-embed"
    assert spec.dimension == 1536


# ---------------------------------------------------------------------------
# Gemini embedding adapter (fake SDK)
# ---------------------------------------------------------------------------

def _gemini_provider(dimension=4):
    spec = EmbeddingModelSpec(
        provider="gemini", model="gemini-embedding-001", dimension=dimension
    )
    return GeminiEmbeddingProvider(api_key_provider=lambda: "test-key", spec=spec)


def test_gemini_adapter_returns_vectors(monkeypatch):
    calls = install_fake_genai(
        monkeypatch,
        [FakeEmbedContentResponse([FakeContentEmbedding([0.5] * 4, token_count=7)])],
    )
    response = _gemini_provider().embed(
        EmbeddingRequest.single("battery", task_type=EmbeddingTaskType.RETRIEVAL_QUERY)
    )
    assert response.success is True
    assert response.provider == "gemini"
    assert response.model == "gemini-embedding-001"
    assert response.vectors[0] == [0.5] * 4
    assert response.usage.total_tokens == 7
    # Provider-neutral config was forwarded to the SDK.
    assert calls[0]["config"]["task_type"] == "RETRIEVAL_QUERY"
    assert calls[0]["config"]["output_dimensionality"] == 4


def test_gemini_adapter_empty_embeddings_fails(monkeypatch):
    install_fake_genai(monkeypatch, [FakeEmbedContentResponse([])])
    response = _gemini_provider().embed(EmbeddingRequest.single("text"))
    assert response.success is False
    assert response.error_type is EmbeddingErrorType.EMPTY_RESPONSE


def test_gemini_adapter_embedding_without_values_fails(monkeypatch):
    install_fake_genai(monkeypatch, [FakeEmbedContentResponse([FakeContentEmbedding([])])])
    response = _gemini_provider().embed(EmbeddingRequest.single("text"))
    assert response.success is False
    assert response.error_type is EmbeddingErrorType.EMPTY_RESPONSE


def test_gemini_adapter_normalizes_rate_limit(monkeypatch):
    install_fake_genai(monkeypatch, [RuntimeError("429 RESOURCE_EXHAUSTED quota")])
    response = _gemini_provider().embed(EmbeddingRequest.single("text"))
    assert response.success is False
    assert response.error_type is EmbeddingErrorType.RATE_LIMIT


def test_gemini_adapter_normalizes_timeout(monkeypatch):
    install_fake_genai(monkeypatch, [TimeoutError("deadline exceeded")])
    response = _gemini_provider().embed(EmbeddingRequest.single("text"))
    assert response.success is False
    assert response.error_type is EmbeddingErrorType.TIMEOUT


def test_gemini_adapter_configured_flag(monkeypatch):
    provider = GeminiEmbeddingProvider(
        api_key_provider=lambda: "your_gemini_api_key_here"
    )
    assert provider.is_configured() is False
    provider = GeminiEmbeddingProvider(api_key_provider=lambda: "real-key")
    assert provider.is_configured() is True


def test_gemini_adapter_missing_sdk_raises_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "google", None)
    with pytest.raises(ImportError):
        _gemini_provider().embed(EmbeddingRequest.single("text"))


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

def test_classify_embedding_error_reuses_shared_classifier():
    assert classify_embedding_error(RuntimeError("429 quota")) is EmbeddingErrorType.RATE_LIMIT
    assert classify_embedding_error(TimeoutError("timed out")) is EmbeddingErrorType.TIMEOUT
    assert (
        classify_embedding_error(RuntimeError("UNAUTHENTICATED api_key invalid"))
        is EmbeddingErrorType.AUTHENTICATION
    )
    assert (
        classify_embedding_error(
            EmbeddingError("x", EmbeddingErrorType.DIMENSION_MISMATCH)
        )
        is EmbeddingErrorType.DIMENSION_MISMATCH
    )
