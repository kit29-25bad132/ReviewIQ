"""Phase 5E — real review pagination integration tests (live Supabase).

Contract: GET /api/products/{product_id}/reviews?page=&page_size=&sort=
&filter_rating=. Filtering, sorting, and pagination must all happen in SQL,
and every count is compared against a direct DB query in the same test.
"""

from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from services.catalog.catalog_service import canonical_catalog

client = TestClient(app)
no_raise_client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    """Restore the live DSN that conftest's hermetic fixture removes."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    dsn = dotenv_values(env_path).get("DATABASE_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)
    if not canonical_catalog.is_configured():
        pytest.skip("live Supabase DSN not configured")


def _count(source_product_id: str, rating: int | None = None) -> int:
    sql = """
        SELECT COUNT(*) FROM public.reviews r
        JOIN public.products p ON r.product_id = p.id
        WHERE p.source_product_id = %s
    """
    params: list = [source_product_id]
    if rating is not None:
        sql += " AND r.rating = %s"
        params.append(rating)
    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql + ";", tuple(params))
            return int(cur.fetchone()[0])


def _page(**params):
    resp = client.get("/api/products/P12/reviews", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_page_size_totals_and_legacy_aliases():
    body = _page(page=1, page_size=20)
    assert body["total_count"] == _count("P12") == 95
    assert body["page_size"] == 20
    assert body["page"] == 1
    assert body["total_pages"] == 5
    assert len(body["items"]) == 20
    # Legacy aliases still populated for pre-5H clients.
    assert body["total"] == body["total_count"]
    assert body["limit"] == body["page_size"]


def test_legacy_limit_and_rating_aliases_still_work():
    body = _page(limit=10, rating=5)
    assert body["page_size"] == 10
    assert body["total_count"] == _count("P12", rating=5)
    assert len(body["items"]) == 10
    assert all(r["rating"] == 5 for r in body["items"])


def test_default_page_size_is_twenty():
    body = _page()
    assert body["page_size"] == 20
    assert len(body["items"]) == 20


def test_pagination_never_duplicates_or_drops_rows():
    first = _page(page=1, page_size=50)
    second = _page(page=2, page_size=50)
    assert first["total_count"] == second["total_count"] == 95
    ids1 = {r["id"] for r in first["items"]}
    ids2 = {r["id"] for r in second["items"]}
    assert len(ids1) == 50 and len(ids2) == 45
    assert not (ids1 & ids2)
    assert len(ids1 | ids2) == 95


def test_page_beyond_last_is_empty_but_keeps_totals():
    body = _page(page=99, page_size=20)
    assert body["items"] == []
    assert body["total_count"] == 95
    assert body["total_pages"] == 5


def test_filter_rating_matches_direct_db_count():
    for star in (1, 2, 3, 4, 5):
        body = _page(filter_rating=star, page_size=100)
        expected = _count("P12", rating=star)
        assert body["total_count"] == expected
        assert all(r["rating"] == star for r in body["items"])


def test_filter_rating_combined_with_sentiment():
    body = _page(filter_rating=5, sentiment="positive", page_size=100)
    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM public.reviews r
                JOIN public.products p ON r.product_id = p.id
                WHERE p.source_product_id = 'P12' AND r.rating = 5
                  AND lower(COALESCE(r.metadata->>'sentiment', 'neutral')) = 'positive';
                """
            )
            expected = int(cur.fetchone()[0])
    assert body["total_count"] == expected
    assert all(r["rating"] == 5 for r in body["items"])
    assert all(r["sentiment"] == "positive" for r in body["items"])


@pytest.mark.parametrize("sort,key", [("rating_desc", "rating"), ("rating_asc", "rating")])
def test_rating_sorts_are_monotonic(sort, key):
    body = _page(sort=sort, page_size=100)
    ratings = [r[key] for r in body["items"]]
    assert ratings == sorted(ratings, reverse=(sort == "rating_desc"))


@pytest.mark.parametrize(
    "sort,reverse",
    [("date_desc", True), ("date_asc", False)],
)
def test_date_sorts_are_monotonic_at_the_service_level(sort, reverse):
    """ReviewItem has no date field, so ordering is checked on the service output."""
    reviews, _ = canonical_catalog.get_reviews("P12", page=1, page_size=100, sort_by=sort)
    dates = [r["review_date"] for r in reviews if r["review_date"]]
    assert dates == sorted(dates, reverse=reverse)


def test_sort_is_applied_to_every_page_not_just_the_first():
    """Sorting must be in the SQL query, so page 2 continues the same order."""
    p1 = _page(sort="rating_desc", page=1, page_size=20)
    p2 = _page(sort="rating_desc", page=2, page_size=20)
    combined = [r["rating"] for r in p1["items"] + p2["items"]]
    assert combined == sorted(combined, reverse=True)


def test_unknown_product_returns_404():
    resp = no_raise_client.get("/api/products/NONEXISTENT_99999/reviews")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_invalid_sort_is_rejected():
    resp = no_raise_client.get("/api/products/P12/reviews", params={"sort": "bogus"})
    assert resp.status_code == 422


def test_invalid_page_size_is_rejected():
    resp = no_raise_client.get("/api/products/P12/reviews", params={"page_size": 0})
    assert resp.status_code == 422
