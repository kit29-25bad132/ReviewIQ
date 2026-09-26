"""V2-P2 tests: /api/v2/retrieval endpoints (offline, no DB/network)."""

from fastapi.testclient import TestClient

from main import app
from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.embeddings.registry import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingModelSpec,
)
from services.embeddings.service import EmbeddingService
from services.retrieval.indexing_service import ReviewIndexingService
from services.retrieval.search_service import SemanticSearchService
from tests.retrieval_fakes import FakeEmbeddingProvider, InMemoryVectorRepository

client = TestClient(app, raise_server_exceptions=False)


def _wired_service():
    dimension = 16
    provider = FakeEmbeddingProvider(dimension=dimension)
    repository = InMemoryVectorRepository()
    embedding = EmbeddingService(
        provider,
        spec=EmbeddingModelSpec(
            provider="fake", model="fake-embed", dimension=dimension
        ),
    )
    indexer = ReviewIndexingService(embedding, repository)
    indexer.index(
        [
            {"review_id": "r1", "product_id": "p1", "review_text": "The battery drains quickly.", "rating": 1},
            {"review_id": "r2", "product_id": "p1", "review_text": "Battery life is excellent.", "rating": 5},
        ]
    )
    return SemanticSearchService(embedding, repository)


def test_status_endpoint_reports_configuration(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_DIMENSION", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    resp = client.get("/api/v2/retrieval/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["embedding_model"] == DEFAULT_EMBEDDING_MODEL
    assert body["embedding_dimension"] == DEFAULT_EMBEDDING_DIMENSION
    assert body["similarity_metric"] == "cosine"
    assert body["database_configured"] is False


def test_search_returns_results(monkeypatch):
    monkeypatch.setattr(
        "routes.retrieval.build_search_service", lambda: _wired_service()
    )
    resp = client.post(
        "/api/v2/retrieval/search", json={"query": "battery drains", "top_k": 2}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["result_count"] >= 1
    assert body["results"][0]["review_text"]
    assert "similarity" in body["results"][0]
    assert "distance" in body["results"][0]


def test_search_not_configured_returns_safe_503(monkeypatch):
    def _unconfigured():
        raise EmbeddingError(
            "Database is not configured. Set DATABASE_URL.",
            EmbeddingErrorType.CONFIGURATION,
        )

    monkeypatch.setattr("routes.retrieval.build_search_service", _unconfigured)
    resp = client.post("/api/v2/retrieval/search", json={"query": "battery"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Semantic retrieval is not configured on the server."
    assert "DATABASE_URL" not in resp.text


def test_search_rejects_empty_query(monkeypatch):
    resp = client.post("/api/v2/retrieval/search", json={"query": "   "})
    assert resp.status_code == 422


def test_search_rejects_invalid_rating_range(monkeypatch):
    resp = client.post(
        "/api/v2/retrieval/search",
        json={"query": "battery", "min_rating": 4, "max_rating": 2},
    )
    assert resp.status_code == 422


def test_search_rejects_out_of_bounds_top_k(monkeypatch):
    assert client.post(
        "/api/v2/retrieval/search", json={"query": "battery", "top_k": 0}
    ).status_code == 422
    assert client.post(
        "/api/v2/retrieval/search", json={"query": "battery", "top_k": 500}
    ).status_code == 422
