"""Phase 5A — Real Statistics Engine (no AI).

Every number returned by :func:`compute_statistics` is produced by ONE SQL
aggregate over ``public.reviews`` in the canonical Supabase database (see
:data:`PRODUCT_STATISTICS_SQL`). Nothing is cached, defaulted, extrapolated,
in-memory filtered, or read from a fallback store.

Two outcomes are kept explicitly distinct, because the API contract (5F/5G)
must tell them apart:

* unknown ``product_id``      -> ``None``            (caller returns 404)
* known product, zero reviews -> statistics of zeros (caller returns zeros,
  never a 404)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.catalog.catalog_service import canonical_catalog

#: One aggregate query per product.
#:
#: * ``rating`` is constrained to 1-5 by a DB check constraint, so the FILTER
#:   counts are exhaustive and their sum equals ``total_reviews`` exactly.
#: * ``average_rating`` is rounded to 1 decimal place IN SQL, never in Python:
#:   float repr makes Python and Postgres disagree at rounding boundaries, and
#:   the integration tests compare this value against a direct DB query.
#: * Sentiment aggregates the ``sentiment`` label already stored on each review
#:   row (``metadata->>'sentiment'``), written by the ingestion pipeline for
#:   every row. Missing/unknown labels fold into ``neutral`` via COALESCE, so
#:   the three buckets always sum to ``total_reviews``.
#: * ``review_date`` is ISO-8601 TEXT, so MIN/MAX are ordered correctly.
PRODUCT_STATISTICS_SQL = """
    SELECT
        COUNT(*)                                                    AS total_reviews,
        COALESCE(ROUND(AVG(r.rating)::numeric, 1), 0.0)             AS average_rating,
        COUNT(*) FILTER (WHERE r.rating = 1)                        AS star_1,
        COUNT(*) FILTER (WHERE r.rating = 2)                        AS star_2,
        COUNT(*) FILTER (WHERE r.rating = 3)                        AS star_3,
        COUNT(*) FILTER (WHERE r.rating = 4)                        AS star_4,
        COUNT(*) FILTER (WHERE r.rating = 5)                        AS star_5,
        COUNT(*) FILTER (WHERE r.verified_purchase)                 AS verified_purchase_count,
        COALESCE(
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE r.verified_purchase)
                / NULLIF(COUNT(*), 0),
                1
            ),
            0.0
        )                                                           AS verified_purchase_pct,
        COUNT(*) FILTER (
            WHERE COALESCE(lower(r.metadata->>'sentiment'), 'neutral') = 'positive'
        )                                                           AS sentiment_positive,
        COUNT(*) FILTER (
            WHERE COALESCE(lower(r.metadata->>'sentiment'), 'neutral') = 'negative'
        )                                                           AS sentiment_negative,
        COUNT(*) FILTER (
            WHERE COALESCE(lower(r.metadata->>'sentiment'), 'neutral')
                  NOT IN ('positive', 'negative')
        )                                                           AS sentiment_neutral,
        MIN(r.review_date)                                          AS earliest_review_date,
        MAX(r.review_date)                                          AS latest_review_date
    FROM public.reviews r
    WHERE r.product_id = %s;
"""


@dataclass(frozen=True)
class ReviewDateRange:
    """Earliest/latest review dates for a product (ISO-8601 strings)."""

    earliest: Optional[str]
    latest: Optional[str]

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {"earliest": self.earliest, "latest": self.latest}


@dataclass(frozen=True)
class ProductStatisticsData:
    """Database-derived statistics for one canonical product.

    All counts/ratings below come straight from :data:`PRODUCT_STATISTICS_SQL`.
    ``rating_distribution`` is keyed by integer star value (1-5) as the 5F
    contract requires.
    """

    product_id: str
    source_product_id: str
    product_name: str
    category: Optional[str]
    total_reviews: int
    average_rating: float
    rating_distribution: Dict[int, int]
    sentiment_distribution: Dict[str, int]
    verified_purchase_count: int
    verified_purchase_pct: float
    date_range: ReviewDateRange

    @property
    def has_reviews(self) -> bool:
        return self.total_reviews > 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "source_product_id": self.source_product_id,
            "product_name": self.product_name,
            "category": self.category,
            "total_reviews": self.total_reviews,
            "average_rating": self.average_rating,
            "rating_distribution": dict(self.rating_distribution),
            "sentiment_distribution": dict(self.sentiment_distribution),
            "verified_purchase_count": self.verified_purchase_count,
            "verified_purchase_pct": self.verified_purchase_pct,
            "date_range": self.date_range.as_dict(),
        }


def _as_float(value: Any) -> float:
    """Normalize psycopg ``Decimal`` (from ROUND(numeric)) to ``float``."""
    return float(value) if value is not None else 0.0


def aggregate_reviews_for_product(product_uuid: str) -> Dict[str, Any]:
    """Run the single aggregate query for a resolved canonical product UUID.

    Exposed separately from :func:`compute_statistics` so callers/tests can
    aggregate a product UUID directly without a second product lookup. A UUID
    with no reviews yields zeros, not an error.
    """
    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(PRODUCT_STATISTICS_SQL, (product_uuid,))
            row = cur.fetchone()

    (
        total_reviews,
        average_rating,
        star_1,
        star_2,
        star_3,
        star_4,
        star_5,
        verified_purchase_count,
        verified_purchase_pct,
        positive,
        negative,
        neutral,
        earliest,
        latest,
    ) = row

    return {
        "total_reviews": int(total_reviews),
        "average_rating": _as_float(average_rating),
        "rating_distribution": {
            1: int(star_1),
            2: int(star_2),
            3: int(star_3),
            4: int(star_4),
            5: int(star_5),
        },
        "sentiment_distribution": {
            "positive": int(positive),
            "neutral": int(neutral),
            "negative": int(negative),
        },
        "verified_purchase_count": int(verified_purchase_count),
        "verified_purchase_pct": _as_float(verified_purchase_pct),
        "date_range": {"earliest": earliest, "latest": latest},
    }


def compute_statistics(
    product_id_or_source_id: str,
) -> Optional[ProductStatisticsData]:
    """Compute real statistics for a product from the canonical database.

    Returns ``None`` when the product does not exist. When the product exists
    but has no reviews, returns the same structure with all-zero counts (the
    caller decides whether that is a 404 or an "insufficient reviews" state).
    """
    product = canonical_catalog.get_product_by_id(str(product_id_or_source_id).strip())
    if product is None:
        return None

    aggregate = aggregate_reviews_for_product(product["id"])

    return ProductStatisticsData(
        product_id=product["id"],
        source_product_id=product["source_product_id"],
        product_name=product["product_title"],
        category=product.get("category"),
        total_reviews=aggregate["total_reviews"],
        average_rating=aggregate["average_rating"],
        rating_distribution=aggregate["rating_distribution"],
        sentiment_distribution=aggregate["sentiment_distribution"],
        verified_purchase_count=aggregate["verified_purchase_count"],
        verified_purchase_pct=aggregate["verified_purchase_pct"],
        date_range=ReviewDateRange(
            earliest=aggregate["date_range"]["earliest"],
            latest=aggregate["date_range"]["latest"],
        ),
    )
