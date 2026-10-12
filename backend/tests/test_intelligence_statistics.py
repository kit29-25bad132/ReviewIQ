"""Phase 5A — Real Statistics Engine integration tests (live Supabase).

Every assertion compares :mod:`services.intelligence.statistics` output
against a direct SQL query executed in the same test, so no statistic can
drift from the database unnoticed. No mocks, no fixtures rows: the product
under test (P12 "Kelto Gamer 16") is a real canonical record.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values

from services.catalog.catalog_service import canonical_catalog
from services.intelligence.statistics import (
    aggregate_reviews_for_product,
    compute_statistics,
)

KELTO_SOURCE_IDS = ("P12", "P02", "P07")


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    """Restore the live DSN that conftest's hermetic fixture removes."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    dsn = dotenv_values(env_path).get("DATABASE_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)
    if not canonical_catalog.is_configured():
        pytest.skip("live Supabase DSN not configured")


def _one(sql: str, params: tuple = ()):
    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def _review_aggregate(source_product_id: str):
    """Direct DB truth for one product, computed independently of the service."""
    return _one(
        """
        SELECT
            COUNT(*),
            COALESCE(ROUND(AVG(r.rating)::numeric, 1), 0.0),
            COUNT(*) FILTER (WHERE r.rating = 1),
            COUNT(*) FILTER (WHERE r.rating = 2),
            COUNT(*) FILTER (WHERE r.rating = 3),
            COUNT(*) FILTER (WHERE r.rating = 4),
            COUNT(*) FILTER (WHERE r.rating = 5),
            COUNT(*) FILTER (WHERE r.verified_purchase),
            COUNT(*) FILTER (
                WHERE COALESCE(lower(r.metadata->>'sentiment'), 'neutral') = 'positive'
            ),
            COUNT(*) FILTER (
                WHERE COALESCE(lower(r.metadata->>'sentiment'), 'neutral') = 'negative'
            ),
            MIN(r.review_date),
            MAX(r.review_date)
        FROM public.reviews r
        JOIN public.products p ON r.product_id = p.id
        WHERE p.source_product_id = %s;
        """,
        (source_product_id,),
    )


def test_p12_statistics_match_direct_db_aggregate():
    stats = compute_statistics("P12")
    assert stats is not None
    assert stats.source_product_id == "P12"
    assert stats.product_name.startswith("Kelto")
    assert stats.category == "Laptop"

    direct = _review_aggregate("P12")
    total, avg, s1, s2, s3, s4, s5, verified, positive, negative, earliest, latest = direct

    assert stats.total_reviews == int(total)
    assert stats.average_rating == float(avg)
    assert stats.rating_distribution == {
        1: int(s1),
        2: int(s2),
        3: int(s3),
        4: int(s4),
        5: int(s5),
    }
    assert stats.sentiment_distribution["positive"] == int(positive)
    assert stats.sentiment_distribution["negative"] == int(negative)
    assert stats.sentiment_distribution["neutral"] == int(total) - int(positive) - int(negative)
    assert stats.verified_purchase_count == int(verified)
    assert stats.date_range.earliest == earliest
    assert stats.date_range.latest == latest

    # Cross-check against the raw table, independent of the aggregate above.
    raw = _one("SELECT COUNT(*) FROM public.reviews WHERE source_product_id = %s;", ("P12",))
    assert stats.total_reviews == int(raw[0])


def test_verified_purchase_pct_matches_db():
    stats = compute_statistics("P12")
    direct = _review_aggregate("P12")
    total, verified = int(direct[0]), int(direct[7])
    expected = round(100.0 * verified / total, 1) if total else 0.0
    assert stats.verified_purchase_pct == pytest.approx(expected, abs=0.05)


def test_average_rating_is_rounded_to_one_decimal_place():
    for source_id in KELTO_SOURCE_IDS:
        stats = compute_statistics(source_id)
        assert stats.average_rating == round(stats.average_rating, 1)
        # And it must equal the DB-rounded value, not a Python-rounded one.
        direct = _review_aggregate(source_id)
        assert stats.average_rating == float(direct[1])


def test_distributions_are_exhaustive_and_sum_to_total():
    for source_id in KELTO_SOURCE_IDS:
        stats = compute_statistics(source_id)
        assert sorted(stats.rating_distribution.keys()) == [1, 2, 3, 4, 5]
        assert sum(stats.rating_distribution.values()) == stats.total_reviews
        assert sum(stats.sentiment_distribution.values()) == stats.total_reviews
        assert set(stats.sentiment_distribution.keys()) == {"positive", "neutral", "negative"}


def test_date_range_is_absolute_for_every_kelto_product():
    for source_id in KELTO_SOURCE_IDS:
        stats = compute_statistics(source_id)
        direct = _review_aggregate(source_id)
        assert stats.date_range.earliest == direct[10]
        assert stats.date_range.latest == direct[11]
        assert stats.date_range.earliest <= stats.date_range.latest


def test_statistics_differ_between_products():
    """Two real products with different review sets must not share statistics."""
    gamer = compute_statistics("P12")
    pixel = compute_statistics("P02")
    assert gamer.total_reviews != pixel.total_reviews or (
        gamer.average_rating != pixel.average_rating
        or gamer.rating_distribution != pixel.rating_distribution
    )


def test_unknown_product_returns_none():
    assert compute_statistics("NONEXISTENT_99999") is None


def test_aggregate_without_reviews_returns_zeros():
    """A resolved product UUID with no reviews yields zeros, never an error."""
    stats = aggregate_reviews_for_product(str(uuid4()))
    assert stats["total_reviews"] == 0
    assert stats["average_rating"] == 0.0
    assert stats["rating_distribution"] == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    assert stats["sentiment_distribution"] == {"positive": 0, "neutral": 0, "negative": 0}
    assert stats["verified_purchase_count"] == 0
    assert stats["verified_purchase_pct"] == 0.0
    assert stats["date_range"] == {"earliest": None, "latest": None}
