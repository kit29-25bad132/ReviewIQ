"""Authoritative Supabase PostgreSQL Catalog Service for ReviewIQ.

This service is the sole data access layer for all canonical products, reviews,
and catalog analytics, eliminating runtime dependencies on SQLite and CSV.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.retrieval.database import PostgresDatabase
from services.catalog.models import (
    CanonicalProduct,
    CanonicalReview,
    CatalogScanResult,
)

logger = logging.getLogger(__name__)


class CanonicalCatalogService:
    """Catalog service operating directly on Supabase PostgreSQL canonical schema."""

    def __init__(self, db: Optional[PostgresDatabase] = None) -> None:
        self.db = db or PostgresDatabase()

    def is_configured(self) -> bool:
        return self.db.is_configured()

    def scan_current_catalog_state(self) -> CatalogScanResult:
        """Inspects and returns the live catalog state in Supabase."""
        result = CatalogScanResult()
        if not self.is_configured():
            result.status_summary = "Database is not configured (missing DATABASE_URL)"
            return result

        try:
            with self.db.connection() as conn:
                result.database_connected = True
                with conn.cursor() as cur:
                    # Products count
                    cur.execute("SELECT COUNT(*) FROM public.products;")
                    result.total_products = cur.fetchone()[0]

                    # Reviews count
                    cur.execute("SELECT COUNT(*) FROM public.reviews;")
                    result.total_reviews = cur.fetchone()[0]

                    # Embeddings count
                    try:
                        cur.execute("SELECT COUNT(*) FROM public.review_embeddings;")
                        result.total_embeddings = cur.fetchone()[0]
                    except Exception:
                        result.total_embeddings = 0

                    # Orphan reviews count (reviews where product_id not in products)
                    cur.execute("""
                        SELECT COUNT(*) 
                        FROM public.reviews r
                        LEFT JOIN public.products p ON r.product_id = p.id
                        WHERE p.id IS NULL;
                    """)
                    result.orphan_reviews_count = cur.fetchone()[0]

                    # Categories
                    cur.execute("SELECT DISTINCT category FROM public.products ORDER BY category;")
                    result.categories = [row[0] for row in cur.fetchall()]

                    # Brands
                    cur.execute("SELECT DISTINCT brand FROM public.products ORDER BY brand;")
                    result.brands = [row[0] for row in cur.fetchall()]

                    # Latest dataset version & quality status
                    cur.execute("""
                        SELECT dataset_version, status 
                        FROM public.data_quality_reports 
                        ORDER BY created_at DESC 
                        LIMIT 1;
                    """)
                    latest_q = cur.fetchone()
                    if latest_q:
                        result.dataset_version = latest_q[0]
                        result.quality_gate_passed = (latest_q[1] == "PASS")

                result.status_summary = (
                    f"Connected to Supabase PostgreSQL: {result.total_products} products, "
                    f"{result.total_reviews} reviews, {result.total_embeddings} embeddings, "
                    f"{result.orphan_reviews_count} orphans."
                )
        except Exception as exc:
            logger.error("Error scanning catalog state: %s", exc)
            result.status_summary = f"Database scan error: {str(exc)}"

        return result

    def get_products(
        self,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Lists canonical products with dynamically computed statistics."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                where_clauses = []
                params: List[Any] = []

                if category and category.strip():
                    where_clauses.append("p.category = %s")
                    params.append(category.strip())

                if brand and brand.strip():
                    where_clauses.append("p.brand = %s")
                    params.append(brand.strip())

                if search and search.strip():
                    term = f"%{search.strip()}%"
                    where_clauses.append(
                        "(p.name ILIKE %s OR p.brand ILIKE %s OR p.category ILIKE %s OR p.source_product_id ILIKE %s)"
                    )
                    params.extend([term, term, term, term])

                where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

                # Count query
                count_query = f"SELECT COUNT(*) FROM public.products p {where_sql};"
                cur.execute(count_query, params)
                total_count = cur.fetchone()[0]

                # Main query with review aggregation
                query = f"""
                    SELECT 
                        p.id,
                        p.source_product_id,
                        p.name,
                        p.brand,
                        p.category,
                        p.metadata,
                        p.source_dataset,
                        p.source_reference,
                        COALESCE(COUNT(r.id), 0) AS review_count,
                        COALESCE(ROUND(AVG(r.rating)::numeric, 2), 0.0) AS average_rating
                    FROM public.products p
                    LEFT JOIN public.reviews r ON r.product_id = p.id
                    {where_sql}
                    GROUP BY p.id, p.source_product_id, p.name, p.brand, p.category, p.metadata, p.source_dataset, p.source_reference
                    ORDER BY review_count DESC, p.name ASC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, params + [limit, offset])
                rows = cur.fetchall()

                products = []
                for row in rows:
                    p_id, s_pid, name, p_brand, p_cat, meta, src_ds, src_ref, r_cnt, avg_r = row
                    meta_dict = meta if isinstance(meta, dict) else (json.loads(meta) if meta else {})
                    products.append({
                        "id": str(p_id),
                        "product_id": s_pid,
                        "source_product_id": s_pid,
                        "product_title": name,
                        "name": name,
                        "brand": p_brand,
                        "category": p_cat,
                        "price_inr": meta_dict.get("price_inr", 0.0),
                        "review_count": int(r_cnt),
                        "average_rating": float(avg_r),
                        "source_dataset": src_ds,
                        "source_reference": src_ref,
                        "metadata": meta_dict,
                    })

                return products, total_count

    def get_product_by_id(self, product_id_or_source_id: str) -> Optional[Dict[str, Any]]:
        """Finds a product by UUID or source_product_id (e.g. 'P02', 'P12')."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        p.id,
                        p.source_product_id,
                        p.name,
                        p.brand,
                        p.category,
                        p.metadata,
                        p.source_dataset,
                        p.source_reference,
                        COALESCE(COUNT(r.id), 0) AS review_count,
                        COALESCE(ROUND(AVG(r.rating)::numeric, 2), 0.0) AS average_rating
                    FROM public.products p
                    LEFT JOIN public.reviews r ON r.product_id = p.id
                    WHERE p.source_product_id = %s OR p.id::text = %s
                    GROUP BY p.id, p.source_product_id, p.name, p.brand, p.category, p.metadata, p.source_dataset, p.source_reference;
                """, (product_id_or_source_id, product_id_or_source_id))
                row = cur.fetchone()
                if not row:
                    return None

                p_id, s_pid, name, p_brand, p_cat, meta, src_ds, src_ref, r_cnt, avg_r = row
                meta_dict = meta if isinstance(meta, dict) else (json.loads(meta) if meta else {})
                return {
                    "id": str(p_id),
                    "product_id": s_pid,
                    "source_product_id": s_pid,
                    "product_title": name,
                    "name": name,
                    "brand": p_brand,
                    "category": p_cat,
                    "price_inr": meta_dict.get("price_inr", 0.0),
                    "review_count": int(r_cnt),
                    "average_rating": float(avg_r),
                    "source_dataset": src_ds,
                    "source_reference": src_ref,
                    "metadata": meta_dict,
                }

    def get_product_statistics(self, product_id_or_source_id: str) -> Optional[Dict[str, Any]]:
        """Calculates detailed rating distribution and sentiment metrics for a product."""
        product = self.get_product_by_id(product_id_or_source_id)
        if not product:
            return None

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # Rating distribution
                cur.execute("""
                    SELECT rating, COUNT(*) 
                    FROM public.reviews 
                    WHERE source_product_id = %s OR product_id::text = %s
                    GROUP BY rating
                    ORDER BY rating;
                """, (product["source_product_id"], product["id"]))
                rating_counts = {int(r): int(cnt) for r, cnt in cur.fetchall()}

                # Fetch metadata for sentiment and aspect distribution
                cur.execute("""
                    SELECT metadata, verified_purchase
                    FROM public.reviews 
                    WHERE source_product_id = %s OR product_id::text = %s;
                """, (product["source_product_id"], product["id"]))
                review_rows = cur.fetchall()

                sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
                verified_count = 0
                aspect_counts: Dict[str, Dict[str, int]] = {}

                for meta_raw, verified in review_rows:
                    if verified:
                        verified_count += 1
                    meta = meta_raw if isinstance(meta_raw, dict) else (json.loads(meta_raw) if meta_raw else {})
                    sent = (meta.get("sentiment") or "neutral").lower()
                    if sent in sentiment_counts:
                        sentiment_counts[sent] += 1
                    else:
                        sentiment_counts["neutral"] += 1

                    # Aspect sentiments
                    aspect_sentiments = meta.get("aspect_sentiments") or {}
                    if isinstance(aspect_sentiments, dict):
                        for aspect, a_sent in aspect_sentiments.items():
                            if aspect not in aspect_counts:
                                aspect_counts[aspect] = {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
                            a_s_clean = str(a_sent).lower()
                            if a_s_clean in ("positive", "pos"):
                                aspect_counts[aspect]["positive"] += 1
                            elif a_s_clean in ("negative", "neg"):
                                aspect_counts[aspect]["negative"] += 1
                            else:
                                aspect_counts[aspect]["neutral"] += 1
                            aspect_counts[aspect]["total"] += 1

                total_reviews = product["review_count"]
                star_dist = {f"star_{i}": rating_counts.get(i, 0) for i in range(1, 6)}
                verified_pct = round((verified_count / total_reviews * 100), 1) if total_reviews > 0 else 0.0

                return {
                    "product": product,
                    "total_reviews": total_reviews,
                    "average_rating": product["average_rating"],
                    "rating_distribution": star_dist,
                    "sentiment_distribution": sentiment_counts,
                    "verified_purchase_percentage": verified_pct,
                    "aspect_sentiment_summary": aspect_counts,
                }

    def get_reviews(
        self,
        product_id_or_source_id: str,
        rating: Optional[int] = None,
        sentiment: Optional[str] = None,
        verified_only: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "recent",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Returns paginated canonical reviews for a product."""
        product = self.get_product_by_id(product_id_or_source_id)
        if not product:
            return [], 0

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                where_clauses = ["(r.source_product_id = %s OR r.product_id::text = %s)"]
                params: List[Any] = [product["source_product_id"], product["id"]]

                if rating is not None:
                    where_clauses.append("r.rating = %s")
                    params.append(rating)

                if verified_only is not None:
                    where_clauses.append("r.verified_purchase = %s")
                    params.append(verified_only)

                if sentiment and sentiment.strip():
                    where_clauses.append("r.metadata->>'sentiment' = %s")
                    params.append(sentiment.strip().lower())

                where_sql = "WHERE " + " AND ".join(where_clauses)

                # Count query
                cur.execute(f"SELECT COUNT(*) FROM public.reviews r {where_sql};", params)
                total_reviews = cur.fetchone()[0]

                # Sorting
                if sort_by == "highest_rating":
                    order_sql = "ORDER BY r.rating DESC, r.created_at DESC"
                elif sort_by == "lowest_rating":
                    order_sql = "ORDER BY r.rating ASC, r.created_at DESC"
                elif sort_by == "helpful":
                    order_sql = "ORDER BY (COALESCE((r.metadata->>'helpful_votes')::int, 0)) DESC, r.created_at DESC"
                else:
                    order_sql = "ORDER BY r.review_date DESC NULLS LAST, r.created_at DESC"

                offset = (page - 1) * page_size
                query = f"""
                    SELECT 
                        r.id,
                        r.product_id,
                        r.source_product_id,
                        r.source_review_id,
                        r.rating,
                        r.review_title,
                        r.review_text,
                        r.review_date,
                        r.verified_purchase,
                        r.source_dataset,
                        r.source_reference,
                        r.metadata,
                        r.created_at
                    FROM public.reviews r
                    {where_sql}
                    {order_sql}
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, params + [page_size, offset])
                rows = cur.fetchall()

                reviews = []
                for row in rows:
                    r_id, p_id, s_pid, s_rid, rating_val, title, text, r_date, verified, src_ds, src_ref, meta, created = row
                    meta_dict = meta if isinstance(meta, dict) else (json.loads(meta) if meta else {})
                    reviews.append({
                        "id": str(r_id),
                        "review_id": s_rid,
                        "source_review_id": s_rid,
                        "product_id": s_pid,
                        "source_product_id": s_pid,
                        "canonical_product_id": str(p_id),
                        "rating": rating_val,
                        "review_title": title or "",
                        "review_text": text,
                        "review_date": r_date or "",
                        "verified_purchase": verified,
                        "helpful_votes": int(meta_dict.get("helpful_votes", 0)),
                        "sentiment": meta_dict.get("sentiment", "neutral"),
                        "aspects_mentioned": meta_dict.get("aspects_mentioned", []),
                        "aspect_sentiments": meta_dict.get("aspect_sentiments", {}),
                        "source_dataset": src_ds,
                        "source_reference": src_ref,
                        "metadata": meta_dict,
                    })

                return reviews, total_reviews

    def get_categories(self) -> List[str]:
        """Returns distinct categories in the canonical dataset."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT category FROM public.products ORDER BY category;")
                return [row[0] for row in cur.fetchall()]

    def get_brands(self) -> List[str]:
        """Returns distinct brands in the canonical dataset."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT brand FROM public.products ORDER BY brand;")
                return [row[0] for row in cur.fetchall()]


# Singleton instance
canonical_catalog = CanonicalCatalogService()
