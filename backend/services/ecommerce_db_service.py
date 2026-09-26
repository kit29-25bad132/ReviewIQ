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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def is_ready(self) -> bool:
        if not self.db_path.exists():
            try:
                from scripts.seed_sample_data import seed_database
                seed_database()
            except Exception:
                pass
        return self.db_path.exists()

    def search_products(self, query: str, limit: int = 20) -> List[ProductSummary]:
        if not self.is_ready():
            return []

        q_clean = query.strip()
        if not q_clean:
            # Return top popular products if empty query
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT product_id, product_title, category, review_count, average_rating
                    FROM products
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
            finally:
                conn.close()

        q_lower = q_clean.lower()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Priority 1: Exact match on title
            cursor.execute("""
                SELECT product_id, product_title, category, review_count, average_rating
                FROM products
                WHERE product_title = ?
                LIMIT ?;
            """, (q_clean, limit))
            exact_matches = cursor.fetchall()

            # Priority 2: Case-insensitive exact match
            cursor.execute("""
                SELECT product_id, product_title, category, review_count, average_rating
                FROM products
                WHERE normalized_title = ?
                LIMIT ?;
            """, (q_lower, limit))
            norm_matches = cursor.fetchall()

            # Priority 3: Prefix match
            cursor.execute("""
                SELECT product_id, product_title, category, review_count, average_rating
                FROM products
                WHERE normalized_title LIKE ? || '%'
                ORDER BY review_count DESC
                LIMIT ?;
            """, (q_lower, limit))
            prefix_matches = cursor.fetchall()

            # Priority 4: Substring match
            cursor.execute("""
                SELECT product_id, product_title, category, review_count, average_rating
                FROM products
                WHERE normalized_title LIKE '%' || ? || '%'
                ORDER BY review_count DESC
                LIMIT ?;
            """, (q_lower, limit))
            substring_matches = cursor.fetchall()

            # Combine preserving priority order with de-duplication by product_id
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
            cursor.execute("""
                SELECT * FROM products WHERE product_id = ?;
            """, (str(product_id),))
            p_row = cursor.fetchone()

            if not p_row:
                return None

            # Fetch top 5 recent reviews
            cursor.execute("""
                SELECT id, product_id, product_title, category, review_text, rating, sentiment
                FROM reviews
                WHERE product_id = ?
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
                "5": p_row["star_5_count"],
                "4": p_row["star_4_count"],
                "3": p_row["star_3_count"],
                "2": p_row["star_2_count"],
                "1": p_row["star_1_count"],
            }

            sentiment_distribution = {
                "positive": p_row["positive_count"],
                "neutral": p_row["neutral_count"],
                "negative": p_row["negative_count"],
            }

            return ProductAnalysisResponse(
                product=ProductSummary(
                    product_id=str(p_row["product_id"]),
                    product_title=p_row["product_title"],
                    category=p_row["category"],
                    review_count=p_row["review_count"],
                    average_rating=p_row["average_rating"],
                ),
                statistics=ProductStatistics(
                    review_count=p_row["review_count"],
                    average_rating=p_row["average_rating"],
                    rating_distribution=rating_distribution,
                    sentiment_distribution=sentiment_distribution,
                ),
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
            params = [str(product_id)]

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

    def get_sample_reviews(self, product_id: str, limit: int = 40) -> List[str]:
        if not self.is_ready():
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT review_text, rating, sentiment
                FROM reviews
                WHERE product_id = ?
                ORDER BY id ASC
                LIMIT ?;
            """, (str(product_id), limit))
            rows = cursor.fetchall()
            return [
                f"[{r['sentiment']} | {r['rating']}★] {r['review_text']}"
                for r in rows
            ]
        finally:
            conn.close()


ecommerce_db_service = EcommerceDBService()
