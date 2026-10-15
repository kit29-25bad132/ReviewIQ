"""Live full-corpus canonical retrieval regression (integration).

Live Supabase + embedding provider required. Run separately from the unit
suite (each test embeds exactly one query; zero corpus writes):

    pytest backend/tests/test_canonical_retrieval_live.py -m integration

Unit runs should deselect this file (`-m "not integration"`) to avoid
live provider calls.
"""

from pathlib import Path

import pytest
from dotenv import dotenv_values

from services.retrieval.runtime import build_search_service
from services.retrieval.vector_repository import ReviewSearchFilters

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def _search(query, top_k=10, **filter_kwargs):
    service = build_search_service()
    filters = ReviewSearchFilters(**filter_kwargs) if filter_kwargs else None
    return service.search(query, top_k=top_k, filters=filters)


def test_product_specific_retrieval_returns_only_p12_canonical_rows():
    outcome = _search("battery life performance", product_id="P12")
    assert len(outcome.results) >= 1
    for result in outcome.results:
        assert result.review_id.startswith("R")
        assert result.product_id == "P12"
        assert result.source == "canonical"


def test_sentiment_filtered_retrieval_respects_max_rating():
    outcome = _search("poor quality disappointing", max_rating=2)
    assert len(outcome.results) >= 1
    for result in outcome.results:
        assert result.rating is not None and result.rating <= 2
        assert result.source == "canonical"


def test_category_scoped_retrieval_ordered_canonical():
    outcome = _search("sound quality audio performance")
    assert len(outcome.results) >= 1
    for result in outcome.results:
        assert result.review_id.startswith("R")
        assert result.source == "canonical"
    similarities = [result.similarity for result in outcome.results]
    assert all(-1.0 <= similarity <= 1.0 for similarity in similarities)
    assert all(first >= second for first, second in zip(similarities, similarities[1:]))


def test_source_filter_exclusion_proof():
    canonical = _search("battery life performance", source="canonical")
    assert len(canonical.results) >= 1
    empty = _search("battery life performance", source="nonexistent_source")
    assert len(empty.results) == 0
