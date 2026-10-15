"""Phase 7G + 7I — RAG evidence tracing and integration tests.

Live tests hit real Supabase (and, where noted, the real Gemini embedding
provider); hermetic tests use the shared offline fakes. No mocks on the
7G/7I-trace paths — a mock would defeat the exit gate.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from services.retrieval.database import PostgresDatabase
from services.rag.similar_reviews import (
    RetrievedReview,
    retrieve_similar_reviews,
)
from services.rag.query_context import build_rag_context

client = TestClient(app)


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def _trace_rows(review_ids):
    db = PostgresDatabase()
    with db.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT source_review_id, review_text FROM reviews "
            "WHERE source_review_id = ANY(%s);",
            (list(review_ids),),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# 7G — evidence tracing (the critical correctness check)
# ---------------------------------------------------------------------------

def test_rag_evidence_is_traceable():
    """Every evidence item returned by the live endpoint must trace to a real
    reviews row whose review_text contains the excerpt verbatim. PASS only
    at 100% traceability."""
    resp = client.post(
        "/api/products/P12/rag-query",
        json={"query": "how is the battery life?", "top_k": 10},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["answer"], "answer must be non-empty"
    assert body["evidence"], "evidence list must be non-empty"

    ids = [item["review_id"] for item in body["evidence"]]
    rows = _trace_rows(ids)

    traced = 0
    for item in body["evidence"]:
        rid = item["review_id"]
        assert rid in rows, f"evidence {rid} has no row in reviews"
        full_text = rows[rid]
        assert item["excerpt"] in full_text, (
            f"excerpt for {rid} is not a substring of review_text"
        )
        traced += 1

    assert traced == len(body["evidence"])
    # Every [review_id] the answer cites must be in the evidence set.
    import re
    cited = set(re.findall(r"\[([R]\d{5}(?:,\s*[R]\d{5})*)\]", body["answer"]))
    flat = {rid.strip() for group in cited for rid in group.split(",")}
    assert flat <= set(ids), f"answer cites ids outside evidence: {flat - set(ids)}"


# ---------------------------------------------------------------------------
# 7I — integration tests
# ---------------------------------------------------------------------------

def test_embedding_dimensions():
    """1. Embed a short text with the real configured provider: 768 dims."""
    from services.retrieval.runtime import build_embedding_service

    service = build_embedding_service()
    vector = service.embed_text("battery life performance test")
    assert len(vector) == 768


def test_retrieval_returns_real_reviews():
    """2. Every retrieved review_id exists in the reviews table."""
    items = retrieve_similar_reviews("battery life performance", "P12")
    assert items, "expected at least one real retrieval result"
    ids = [r.review_id for r in items]
    rows = _trace_rows(ids)
    assert set(ids) <= set(rows.keys())


def test_retrieval_product_filter():
    """3. No returned review belongs to another product."""
    items = retrieve_similar_reviews("battery life performance", "P12")
    assert items
    assert all(r.product_id == "P12" for r in items)
    ids = [r.review_id for r in items]
    db = PostgresDatabase()
    with db.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT source_product_id FROM reviews WHERE source_review_id = ANY(%s);",
            (ids,),
        )
        owners = {row[0] for row in cur.fetchall()}
    assert owners == {"P12"}


def test_context_respects_token_budget():
    """4. Context built with max_tokens=500 stays within 10% tolerance."""
    reviews = tuple(
        RetrievedReview(
            review_id=f"R900{i:03d}",
            review_text=("battery charge cycle and performance notes " * 40) + str(i),
            similarity_score=0.9 - i * 0.01,
            product_id="P12",
            rating=4,
            source_review_id=f"R900{i:03d}",
            source="canonical",
        )
        for i in range(20)
    )
    ctx = build_rag_context(reviews, max_tokens=500)
    assert ctx.token_estimate <= 550
    assert ctx.reviews_truncated >= 1


def test_rag_endpoint_unknown_product():
    """6. POST /rag-query for a non-existent product_id returns 404."""
    resp = client.post(
        "/api/products/NO_SUCH_PRODUCT_999/rag-query",
        json={"query": "battery life?"},
    )
    assert resp.status_code == 404


def test_rag_fallback_on_empty_retrieval():
    """7. Empty retrieval => rag_enabled true, empty answer, empty evidence."""
    from services.rag.similar_reviews import RetrievalOutcome
    from routes import rag_query as rq

    empty = RetrievalOutcome(reviews=(), fallback_triggered=False)
    with (
        patch.object(rq.canonical_catalog, "get_product_by_id", return_value={"product_id": "P12"}),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=empty),
        patch.object(rq, "generate_rag_answer") as answer_mock,
    ):
        resp = client.post(
            "/api/products/P12/rag-query", json={"query": "battery life?"}
        )
    body = resp.json()
    assert body["rag_enabled"] is True
    assert body["answer"] == ""
    assert body["evidence"] == []
    assert body["retrieval_count"] == 0
    answer_mock.assert_not_called()


def test_embedding_resume():
    """8. Index 5 reviews, re-run: only unindexed reviews are processed."""
    from services.embeddings.registry import EmbeddingModelSpec
    from services.embeddings.service import EmbeddingService
    from services.retrieval.contracts import CANONICAL_REVIEW_SOURCE
    from services.retrieval.indexing_service import ReviewIndexingService
    from tests.retrieval_fakes import FakeEmbeddingProvider, InMemoryVectorRepository

    spec = EmbeddingModelSpec(provider="fake", model="fake-embed", dimension=8)
    provider = FakeEmbeddingProvider(dimension=8)
    service = EmbeddingService(provider, spec=spec)
    repository = InMemoryVectorRepository()
    indexer = ReviewIndexingService(service, repository, batch_size=5)

    records = [
        {
            "review_id": f"R9{i:04d}",
            "product_id": "P12",
            "review_text": f"resumable indexing sample review number {i}",
            "rating": 4,
            "sentiment": "positive",
            "source": CANONICAL_REVIEW_SOURCE,
        }
        for i in range(1, 6)
    ]

    first = indexer.index(records)
    assert first.indexed == 5
    assert first.already_indexed == 0
    calls_after_first = len(provider.calls)

    second = indexer.index(records)
    assert second.already_indexed == 5
    assert second.indexed == 0
    assert len(provider.calls) == calls_after_first, (
        "rerun must not re-embed already-indexed reviews"
    )
