"""DuckDB Analytical Profiler for ReviewIQ Datasets.

Generates:
- Total rows, unique products, unique reviews
- Reviews per product distribution (min, max, mean, median, stddev)
- Rating distribution (1 to 5)
- Category & Brand distribution
- Review length statistics (words, characters, min, max, mean, median, p95)
- Temporal distribution (review dates)
- Sentiment distribution
"""

from pathlib import Path
from typing import Any, Dict, List
import duckdb
import pandas as pd


class DuckDBProfiler:
    """Analytical profiling engine powered by DuckDB SQL."""

    def profile_csv(self, csv_path: Path) -> Dict[str, Any]:
        """Runs reproducible analytical profiling directly on the CSV file using DuckDB."""
        path_str = str(csv_path.resolve()).replace("\\", "/")
        con = duckdb.connect(database=":memory:")
        
        try:
            # 1. Basic counts
            counts_query = f"""
                SELECT 
                    COUNT(*) AS total_rows,
                    COUNT(DISTINCT product_id) AS unique_products,
                    COUNT(DISTINCT review_id) AS unique_reviews
                FROM read_csv_auto('{path_str}');
            """
            counts = con.execute(counts_query).df().to_dict(orient="records")[0]

            # 2. Reviews per product distribution
            rpp_query = f"""
                WITH prod_counts AS (
                    SELECT product_id, COUNT(*) AS cnt
                    FROM read_csv_auto('{path_str}')
                    GROUP BY product_id
                )
                SELECT
                    MIN(cnt) AS min_reviews_per_product,
                    MAX(cnt) AS max_reviews_per_product,
                    ROUND(AVG(cnt), 2) AS avg_reviews_per_product,
                    MEDIAN(cnt) AS median_reviews_per_product,
                    ROUND(STDDEV_POP(cnt), 2) AS stddev_reviews_per_product
                FROM prod_counts;
            """
            reviews_per_product = con.execute(rpp_query).df().to_dict(orient="records")[0]

            # 3. Rating distribution
            rating_query = f"""
                SELECT 
                    CAST(rating AS INTEGER) AS rating,
                    COUNT(*) AS count,
                    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS percentage
                FROM read_csv_auto('{path_str}')
                GROUP BY rating
                ORDER BY rating ASC;
            """
            rating_dist = con.execute(rating_query).df().to_dict(orient="records")

            # 4. Category distribution
            category_query = f"""
                SELECT 
                    category,
                    COUNT(*) AS review_count,
                    COUNT(DISTINCT product_id) AS product_count,
                    ROUND(AVG(CAST(rating AS FLOAT)), 2) AS avg_rating
                FROM read_csv_auto('{path_str}')
                GROUP BY category
                ORDER BY review_count DESC;
            """
            category_dist = con.execute(category_query).df().to_dict(orient="records")

            # 5. Brand distribution
            brand_query = f"""
                SELECT 
                    brand,
                    COUNT(*) AS review_count,
                    COUNT(DISTINCT product_id) AS product_count,
                    ROUND(AVG(CAST(rating AS FLOAT)), 2) AS avg_rating
                FROM read_csv_auto('{path_str}')
                GROUP BY brand
                ORDER BY review_count DESC;
            """
            brand_dist = con.execute(brand_query).df().to_dict(orient="records")

            # 6. Review length statistics
            length_query = f"""
                WITH lengths AS (
                    SELECT 
                        LENGTH(review_text) AS char_len,
                        LENGTH(TRIM(review_text)) - LENGTH(REPLACE(TRIM(review_text), ' ', '')) + 1 AS word_len
                    FROM read_csv_auto('{path_str}')
                )
                SELECT
                    MIN(word_len) AS min_word_count,
                    MAX(word_len) AS max_word_count,
                    ROUND(AVG(word_len), 2) AS avg_word_count,
                    MEDIAN(word_len) AS median_word_count,
                    QUANTILE_CONT(word_len, 0.95) AS p95_word_count,
                    MIN(char_len) AS min_char_len,
                    MAX(char_len) AS max_char_len,
                    ROUND(AVG(char_len), 2) AS avg_char_len
                FROM lengths;
            """
            review_lengths = con.execute(length_query).df().to_dict(orient="records")[0]

            # 7. Sentiment distribution
            sentiment_query = f"""
                SELECT 
                    LOWER(sentiment) AS sentiment,
                    COUNT(*) AS count,
                    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS percentage
                FROM read_csv_auto('{path_str}')
                GROUP BY LOWER(sentiment)
                ORDER BY count DESC;
            """
            sentiment_dist = con.execute(sentiment_query).df().to_dict(orient="records")

            # 8. Product summary table
            products_query = f"""
                SELECT 
                    product_id,
                    product_name,
                    brand,
                    category,
                    COUNT(*) AS review_count,
                    ROUND(AVG(CAST(rating AS FLOAT)), 2) AS avg_rating
                FROM read_csv_auto('{path_str}')
                GROUP BY product_id, product_name, brand, category
                ORDER BY product_id ASC;
            """
            products_summary = con.execute(products_query).df().to_dict(orient="records")

            return {
                "counts": counts,
                "reviews_per_product": reviews_per_product,
                "rating_distribution": rating_dist,
                "category_distribution": category_dist,
                "brand_distribution": brand_dist,
                "review_length_statistics": review_lengths,
                "sentiment_distribution": sentiment_dist,
                "products_summary": products_summary,
            }
        finally:
            con.close()


duckdb_profiler = DuckDBProfiler()
