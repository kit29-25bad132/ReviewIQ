"""Shared offline test doubles for the retrieval/embeddings test suite.

Not collected by pytest (no ``test_`` prefix). No network, no database, no
provider SDK required.
"""

import hashlib
import math
import sys
from typing import Dict, List, Optional, Sequence, Set
from unittest import mock

from services.embeddings.contracts import EmbeddingRequest, EmbeddingResponse
from services.embeddings.provider import EmbeddingProvider
from services.retrieval.vector_repository import (
    ReviewSearchFilters,
    ReviewSearchResult,
    ReviewVectorRecord,
    VectorMetadata,
    VectorRepository,
)

DEFAULT_FAKE_DIMENSION = 16


def hashing_vector(text: str, dimension: int) -> List[float]:
    """Deterministic bag-of-words hashing vector so similar text scores higher."""
    vector = [0.0] * dimension
    for token in text.lower().split():
        digest = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        vector[digest % dimension] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class FakeEmbeddingProvider(EmbeddingProvider):
    """In-process embedding provider driven by a script of responses/exceptions."""

    name = "fake"

    def __init__(
        self,
        dimension: int = DEFAULT_FAKE_DIMENSION,
        *,
        configure: bool = True,
        script: Optional[list] = None,
    ) -> None:
        self.dimension = dimension
        self.configure = configure
        self.script = list(script or [])
        self.calls: List[EmbeddingRequest] = []

    def is_configured(self) -> bool:
        return self.configure

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.calls.append(request)
        dimension = request.dimension or self.dimension
        if self.script:
            index = min(len(self.calls) - 1, len(self.script) - 1)
            step = self.script[index]
            if isinstance(step, BaseException):
                raise step
            if isinstance(step, EmbeddingResponse):
                return step
        return EmbeddingResponse(
            vectors=[hashing_vector(text, dimension) for text in request.texts],
            provider=self.name,
            model=request.model or "fake-embed",
            dimension=dimension,
            success=True,
        )


class InMemoryVectorRepository(VectorRepository):
    """Test double implementing cosine similarity in Python."""

    def __init__(self) -> None:
        self._records: Dict[str, ReviewVectorRecord] = {}

    def upsert(self, records: Sequence[ReviewVectorRecord]) -> int:
        for record in records:
            self._records[record.fingerprint] = record
        return len(records)

    def existing_fingerprints(self, fingerprints: Sequence[str]) -> Set[str]:
        return {fp for fp in fingerprints if fp in self._records}

    def search(
        self,
        query_vector: Sequence[float],
        *,
        embedding_model: str,
        dimension: int,
        top_k: int,
        similarity_threshold: Optional[float] = None,
        filters: Optional[ReviewSearchFilters] = None,
    ) -> List[ReviewSearchResult]:
        results: List[ReviewSearchResult] = []
        for record in self._records.values():
            if record.embedding_model != embedding_model:
                continue
            if filters is not None:
                if filters.product_id is not None and record.product_id != filters.product_id:
                    continue
                if filters.min_rating is not None and (
                    record.rating is None or record.rating < filters.min_rating
                ):
                    continue
                if filters.max_rating is not None and (
                    record.rating is None or record.rating > filters.max_rating
                ):
                    continue
                if filters.source is not None and record.source != filters.source:
                    continue
            similarity = cosine_similarity(query_vector, record.embedding)
            if similarity_threshold is not None and similarity < similarity_threshold:
                continue
            results.append(
                ReviewSearchResult(
                    review_id=record.review_id,
                    product_id=record.product_id,
                    review_text=record.original_text,
                    normalized_text=record.normalized_text,
                    similarity=similarity,
                    distance=1.0 - similarity,
                    embedding_model=record.embedding_model,
                    rating=record.rating,
                    source=record.source,
                )
            )
        results.sort(key=lambda item: item.similarity, reverse=True)
        return results[:top_k]

    def get_metadata(self, review_id: str) -> Optional[VectorMetadata]:
        for record in self._records.values():
            if record.review_id == review_id:
                return VectorMetadata(
                    review_id=record.review_id,
                    product_id=record.product_id,
                    rating=record.rating,
                    source=record.source,
                    embedding_model=record.embedding_model,
                    embedding_dimension=record.embedding_dimension,
                )
        return None

    def count(self) -> int:
        return len(self._records)


# ---------------------------------------------------------------------------
# Fake google-genai SDK (embed_content)
# ---------------------------------------------------------------------------

class FakeContentEmbedding:
    def __init__(self, values, token_count=None):
        self.values = values
        if token_count is not None:
            self.statistics = mock.MagicMock(token_count=token_count)


class FakeEmbedContentResponse:
    def __init__(self, embeddings):
        self.embeddings = embeddings


def install_fake_genai(monkeypatch, script: list):
    """Install a fake google-genai module; returns the recorded calls list."""
    calls: list = []
    script = list(script)

    class _Models:
        def embed_content(self, model, contents, config):
            calls.append(
                {"model": model, "contents": list(contents), "config": config}
            )
            index = min(len(calls) - 1, len(script) - 1)
            step = script[index]
            if isinstance(step, BaseException):
                raise step
            return step

    class _Client:
        def __init__(self, api_key):
            self.models = _Models()

    fake_genai = mock.MagicMock()
    fake_genai.Client = lambda api_key: _Client(api_key)
    fake_types = mock.MagicMock()
    # Return the kwargs so tests can assert task_type / output_dimensionality.
    fake_types.EmbedContentConfig = lambda **kwargs: kwargs
    # Make "from google.genai import types" resolve to our fake types module.
    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, "google", mock.MagicMock(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    return calls
