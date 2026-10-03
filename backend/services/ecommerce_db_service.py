import importlib.util
import math
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

from models.ecommerce import (
    ProductSummary,
    ProductStatistics,
    ProductAnalysisResponse,
    ReviewItem,
    ReviewsPaginationResponse,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "ecommerce_reviews.db"


class EcommerceDBService:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database file not found at {self.db_path}. Please run dataset ingestion."
            )
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA cache_size = -32000;")
        cursor.execute("PRAGMA temp_store = MEMORY;")
        cursor.execute("PRAGMA mmap_size = 268435456;")
        return conn

    def ensure_indexes(self) -> None:
        """Ensures high-performance covering indexes exist on reviews and products tables."""
        if not self.db_path.exists():
            return
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_pid_sentiment ON reviews(product_id, sentiment);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_pid_rating ON reviews(product_id, rating);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_pid ON products(product_id);")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def ensure_seed_data(self) -> bool:
        if self.db_path.exists():
            self.ensure_indexes()
            return True

        seed_file = BASE_DIR / "scripts" / "seed_sample_data.py"
        if not seed_file.exists():
            return False

        try:
            spec = importlib.util.spec_from_file_location("reviewiq_seed_data", seed_file)
            if spec is None or spec.loader is None:
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            seed_fn = getattr(module, "seed_database", None)
            if callable(seed_fn):
                seed_fn()
        except Exception:
            return False

        ready = self.db_path.exists()
        if ready:
            self.ensure_indexes()
        return ready

    def is_ready(self) -> bool:
        return self.ensure_seed_data()

    def search_products(self, query: str, limit: int = 20) -> List[ProductSummary]:
        if not self.is_ready():
            return []

        q_clean = query.strip()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            if not q_clean:
                # Return top popular products calculated dynamically from reviews
                cursor.execute("""
                    SELECT
                        product_id,
                        product_title,
                        category,
                        COUNT(*) AS review_count,
                        ROUND(AVG(rating), 2) AS average_rating
                    FROM reviews
                    GROUP BY product_id, product_title, category
                    ORDER BY review_count DESC
                    LIMIT ?;
                """, (limit,))
                rows = cursor.fetchall()
                return [
                    ProductSummary(
                        product_id=str(r["product_id"]),
                        product_title=r["product_title"],
                        category=r["category"],
                        review_count=r["review_count"],
                        average_rating=r["average_rating"],
                    )
                    for r in rows
                ]

            q_lower = q_clean.lower()

            # Priority search across reviews table
            # 1. Exact title match
            cursor.execute("""
                SELECT
                    product_id,
                    product_title,
                    category,
                    COUNT(*) AS review_count,
                    ROUND(AVG(rating), 2) AS average_rating
                FROM reviews
                WHERE product_title = ?
                GROUP BY product_id, product_title, category
                ORDER BY review_count DESC
                LIMIT ?;
            """, (q_clean, limit))
            exact_matches = cursor.fetchall()

            # 2. Case-insensitive exact match
            cursor.execute("""
                SELECT
                    product_id,
                    product_title,
                    category,
                    COUNT(*) AS review_count,
                    ROUND(AVG(rating), 2) AS average_rating
                FROM reviews
                WHERE LOWER(TRIM(product_title)) = ?
                GROUP BY product_id, product_title, category
                ORDER BY review_count DESC
                LIMIT ?;
            """, (q_lower, limit))
            norm_matches = cursor.fetchall()

            # 3. Prefix match
            cursor.execute("""
                SELECT
                    product_id,
                    product_title,
                    category,
                    COUNT(*) AS review_count,
                    ROUND(AVG(rating), 2) AS average_rating
                FROM reviews
                WHERE LOWER(TRIM(product_title)) LIKE ? || '%'
                GROUP BY product_id, product_title, category
                ORDER BY review_count DESC
                LIMIT ?;
            """, (q_lower, limit))
            prefix_matches = cursor.fetchall()

            # 4. Substring match across product title, category, brand, or exact Product ID
            cursor.execute("""
                SELECT
                    product_id,
                    product_title,
                    category,
                    COUNT(*) AS review_count,
                    ROUND(AVG(rating), 2) AS average_rating
                FROM reviews
                WHERE LOWER(TRIM(product_title)) LIKE '%' || ? || '%'
                   OR LOWER(TRIM(category)) LIKE '%' || ? || '%'
                   OR LOWER(TRIM(brand)) LIKE '%' || ? || '%'
                   OR product_id = ?
                GROUP BY product_id, product_title, category
                ORDER BY review_count DESC
                LIMIT ?;
            """, (q_lower, q_lower, q_lower, q_clean, limit))
            substring_matches = cursor.fetchall()

            seen = set()
            results: List[ProductSummary] = []
            for group in [exact_matches, norm_matches, prefix_matches, substring_matches]:
                for r in group:
                    pid = str(r["product_id"])
                    if pid not in seen:
                        seen.add(pid)
                        results.append(
                            ProductSummary(
                                product_id=pid,
                                product_title=r["product_title"],
                                category=r["category"],
                                review_count=r["review_count"],
                                average_rating=r["average_rating"],
                            )
                        )
                        if len(results) >= limit:
                            return results

            return results
        finally:
            conn.close()

    def get_product_analysis(self, product_id: str) -> Optional[ProductAnalysisResponse]:
        if not self.is_ready():
            return None

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Dynamically compute factual metrics directly from actual database reviews
            cursor.execute("""
                SELECT
                    product_id,
                    product_title,
                    category,
                    COUNT(*) AS review_count,
                    ROUND(AVG(rating), 2) AS average_rating,
                    SUM(CASE WHEN LOWER(sentiment) = 'positive' THEN 1 ELSE 0 END) AS positive_count,
                    SUM(CASE WHEN LOWER(sentiment) = 'neutral' THEN 1 ELSE 0 END) AS neutral_count,
                    SUM(CASE WHEN LOWER(sentiment) = 'negative' THEN 1 ELSE 0 END) AS negative_count,
                    SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS star_5_count,
                    SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS star_4_count,
                    SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS star_3_count,
                    SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS star_2_count,
                    SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS star_1_count
                FROM reviews
                WHERE product_id = ?
                GROUP BY product_id;
            """, (str(product_id),))
            p_row = cursor.fetchone()

            if not p_row or p_row["review_count"] == 0:
                # Check if product exists in products table but has 0 reviews in reviews table
                return None

            pid = str(p_row["product_id"])
            title = p_row["product_title"]
            category = p_row["category"]
            review_count = p_row["review_count"]
            average_rating = p_row["average_rating"] or 0.0

            # Fetch top recent real reviews for this product
            cursor.execute("""
                SELECT id, product_id, product_title, category, review_text, rating, sentiment
                FROM reviews
                WHERE product_id = ?
                ORDER BY id DESC
                LIMIT 5;
            """, (str(product_id),))
            r_rows = cursor.fetchall()

            recent_reviews = [
                ReviewItem(
                    id=r["id"],
                    product_id=str(r["product_id"]),
                    product_title=r["product_title"],
                    category=r["category"],
                    review_text=r["review_text"],
                    rating=r["rating"],
                    sentiment=r["sentiment"],
                )
                for r in r_rows
            ]

            rating_distribution = {
                "5": p_row["star_5_count"] or 0,
                "4": p_row["star_4_count"] or 0,
                "3": p_row["star_3_count"] or 0,
                "2": p_row["star_2_count"] or 0,
                "1": p_row["star_1_count"] or 0,
            }

            sentiment_distribution = {
                "positive": p_row["positive_count"] or 0,
                "neutral": p_row["neutral_count"] or 0,
                "negative": p_row["negative_count"] or 0,
            }

            summary_item = ProductSummary(
                product_id=pid,
                product_title=title,
                category=category,
                review_count=review_count,
                average_rating=average_rating,
            )
            stats_item = ProductStatistics(
                review_count=review_count,
                average_rating=average_rating,
                rating_distribution=rating_distribution,
                sentiment_distribution=sentiment_distribution,
            )

            return ProductAnalysisResponse(
                product_id=pid,
                product_title=title,
                category=category,
                total_reviews=review_count,
                average_rating=average_rating,
                rating_distribution=rating_distribution,
                sentiment=sentiment_distribution,
                pros=[],
                cons=[],
                summary=f"Analysis of {review_count} verified customer reviews for {title}.",
                insights=[],
                evidence=[],
                ai_available=False,
                product=summary_item,
                statistics=stats_item,
                recent_reviews=recent_reviews,
            )
        finally:
            conn.close()

    def get_product_reviews(
        self,
        product_id: str,
        page: int = 1,
        limit: int = 20,
        rating: Optional[int] = None,
        sentiment: Optional[str] = None,
    ) -> ReviewsPaginationResponse:
        if not self.is_ready():
            return ReviewsPaginationResponse(
                items=[], total=0, page=page, limit=limit, total_pages=0
            )

        page = max(1, page)
        limit = max(1, min(100, limit))
        offset = (page - 1) * limit

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            query_conditions = ["product_id = ?"]
            params: list = [str(product_id)]

            if rating is not None and 1 <= rating <= 5:
                query_conditions.append("rating = ?")
                params.append(rating)

            if sentiment:
                query_conditions.append("LOWER(sentiment) = ?")
                params.append(sentiment.strip().lower())

            where_clause = " AND ".join(query_conditions)

            # Count total
            cursor.execute(f"SELECT COUNT(*) FROM reviews WHERE {where_clause};", params)
            total = cursor.fetchone()[0]

            # Fetch paginated rows
            cursor.execute(f"""
                SELECT id, product_id, product_title, category, review_text, rating, sentiment
                FROM reviews
                WHERE {where_clause}
                ORDER BY id ASC
                LIMIT ? OFFSET ?;
            """, (*params, limit, offset))

            rows = cursor.fetchall()

            items = [
                ReviewItem(
                    id=r["id"],
                    product_id=str(r["product_id"]),
                    product_title=r["product_title"],
                    category=r["category"],
                    review_text=r["review_text"],
                    rating=r["rating"],
                    sentiment=r["sentiment"],
                )
                for r in rows
            ]

            total_pages = math.ceil(total / limit) if total > 0 else 0

            return ReviewsPaginationResponse(
                items=items,
                total=total,
                page=page,
                limit=limit,
                total_pages=total_pages,
            )
        finally:
            conn.close()

    def get_dataset_version(self, product_id: Optional[str] = None) -> str:
        """Returns a stable dataset version string based on review count and latest review id for product or entire DB."""
        if not self.is_ready():
            return "0_0"
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if product_id:
                cursor.execute("""
                    SELECT COUNT(*), MAX(id), ROUND(AVG(rating), 2)
                    FROM reviews
                    WHERE product_id = ?;
                """, (str(product_id),))
            else:
                cursor.execute("""
                    SELECT COUNT(*), MAX(id), ROUND(AVG(rating), 2)
                    FROM reviews;
                """)
            row = cursor.fetchone()
            if not row or row[0] == 0:
                return "empty"
            return f"{row[0]}_{row[1]}_{row[2]}"
        finally:
            conn.close()

    def get_sample_reviews(self, product_id: str, limit: int = 20) -> List[str]:
        if not self.is_ready():
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            rows = []
            try:
                # Balanced high-signal review sampling across sentiments, prioritizing helpful votes and verified reviews
                cursor.execute("""
                    WITH ranked_reviews AS (
                        SELECT 
                            id, review_text, rating, sentiment, helpful_votes,
                            ROW_NUMBER() OVER (
                                PARTITION BY LOWER(sentiment) 
                                ORDER BY helpful_votes DESC, id DESC
                            ) AS rn
                        FROM reviews
                        WHERE product_id = ?
                    )
                    SELECT id, review_text, rating, sentiment
                    FROM ranked_reviews
                    WHERE rn <= 8
                    ORDER BY id ASC
                    LIMIT ?;
                """, (str(product_id), limit))
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                rows = []

            if not rows:
                cursor.execute("""
                    SELECT id, review_text, rating, sentiment
                    FROM reviews
                    WHERE product_id = ?
                    ORDER BY id ASC
                    LIMIT ?;
                """, (str(product_id), limit))
                rows = cursor.fetchall()

            return [
                f"[Review #{r['id']} | {r['sentiment']} | {r['rating']}★] {r['review_text']}"
                for r in rows
            ]
        finally:
            conn.close()


ecommerce_db_service = EcommerceDBService()


