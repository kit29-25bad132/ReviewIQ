import logging
import math
import sqlite3
from pathlib import Path
from typing import List, Optional

from models.ecommerce import (
    ProConTheme,
    ProsConsAnalysisResponse,
    ReviewItem,
)
from services.ecommerce_db_service import ecommerce_db_service

logger = logging.getLogger(__name__)

# Thematic keyword clusters mapped to natural theme titles
PRO_THEME_PATTERNS = [
    {
        "theme": "Quality & Durability",
        "keywords": ["quality", "durable", "solid", "well made", "excellent", "sturdy", "premium"],
    },
    {
        "theme": "Value for Money & Price",
        "keywords": ["worth", "value", "price", "affordable", "deal", "cheap", "bargain", "money"],
    },
    {
        "theme": "Ease of Use & Convenience",
        "keywords": ["easy", "simple", "convenient", "smooth", "comfortable", "handy", "effortless"],
    },
    {
        "theme": "Fast Shipping & Packaging",
        "keywords": ["shipping", "packaging", "delivery", "arrived", "fast", "packaged", "package"],
    },
    {
        "theme": "Product Performance & Reliability",
        "keywords": ["works", "perfect", "great", "effective", "reliable", "powerful", "recommended", "highly"],
    },
]

CON_THEME_PATTERNS = [
    {
        "theme": "Durability & Breakage Issues",
        "keywords": ["broke", "broken", "poor quality", "fragile", "cheap material", "fell apart", "durability", "damage"],
    },
    {
        "theme": "Defective or Malfunctioning",
        "keywords": ["defective", "not working", "stopped working", "faulty", "failed", "died", "terrible", "worst"],
    },
    {
        "theme": "Pricing & Value Dissatisfaction",
        "keywords": ["overpriced", "expensive", "waste of money", "not worth", "ripoff", "cost"],
    },
    {
        "theme": "Missing Expectations or False Claims",
        "keywords": ["disappointed", "misleading", "not as advertised", "unhappy", "expected better", "dissatisfied"],
    },
    {
        "theme": "Usability & Design Complaints",
        "keywords": ["hard to use", "difficult", "uncomfortable", "loud", "heavy", "clunky", "hot", "heating", "battery"],
    },
]


class ProsConsService:
    def analyze_product_pros_cons(self, product_id: str) -> Optional[ProsConsAnalysisResponse]:
        if not ecommerce_db_service.is_ready():
            return None

        conn = ecommerce_db_service._get_connection()
        try:
            cursor = conn.cursor()

            # 1. Fetch product record
            cursor.execute("SELECT * FROM products WHERE product_id = ?;", (str(product_id),))
            p_row = cursor.fetchone()
            if not p_row:
                return None

            product_title = p_row["product_title"]
            total_reviews = p_row["review_count"]
            avg_rating = p_row["average_rating"]
            pos_count = p_row["positive_count"]
            neu_count = p_row["neutral_count"]
            neg_count = p_row["negative_count"]

            # Sample pool for deep keyword pattern extraction (up to 5,000 reviews for speed)
            cursor.execute("""
                SELECT id, review_text, rating, sentiment
                FROM reviews
                WHERE product_id = ?
                ORDER BY id ASC
                LIMIT 5000;
            """, (str(product_id),))
            sample_rows = cursor.fetchall()
            analyzed_pool_size = len(sample_rows) if sample_rows else total_reviews

            # Extract Pros
            pros: List[ProConTheme] = []
            for cluster in PRO_THEME_PATTERNS:
                matching_rows = []
                for row in sample_rows:
                    if row["sentiment"].lower() == "positive" or row["rating"] >= 4:
                        text_lower = row["review_text"].lower()
                        if any(kw in text_lower for kw in cluster["keywords"]):
                            matching_rows.append(row)

                if matching_rows:
                    # Projection methodology (unchanged; now documented):
                    #   scaling_factor = total_reviews / analyzed_pool_size
                    #   estimated_count = max(raw_matches, raw_matches * scaling_factor)
                    #   percentage denominator = total_reviews (the full product
                    #   review pool, NOT the sample).
                    # The result is an ESTIMATE of full-pool mentions derived
                    # from the sampled matches — never a measured full-pool count.
                    scaling_factor = total_reviews / analyzed_pool_size if analyzed_pool_size > 0 else 1.0
                    raw_count = len(matching_rows)
                    estimated_count = max(raw_count, int(raw_count * scaling_factor))
                    percentage = round((estimated_count / total_reviews) * 100, 1)

                    examples = [r["review_text"] for r in matching_rows[:2]]
                    evidence_ids = [r["id"] for r in matching_rows[:10]]

                    pros.append(
                        ProConTheme(
                            theme=cluster["theme"],
                            review_count=estimated_count,
                            percentage=percentage,
                            example_reviews=examples,
                            evidence_review_ids=evidence_ids,
                        )
                    )

            # Sort Pros by review count descending
            pros.sort(key=lambda x: x.review_count, reverse=True)
            pros = pros[:4]

            # Extract Cons
            cons: List[ProConTheme] = []
            for cluster in CON_THEME_PATTERNS:
                matching_rows = []
                for row in sample_rows:
                    if row["sentiment"].lower() == "negative" or row["rating"] <= 2:
                        text_lower = row["review_text"].lower()
                        if any(kw in text_lower for kw in cluster["keywords"]):
                            matching_rows.append(row)

                if matching_rows:
                    # Same documented projection methodology as pros above.
                    scaling_factor = total_reviews / analyzed_pool_size if analyzed_pool_size > 0 else 1.0
                    raw_count = len(matching_rows)
                    estimated_count = max(raw_count, int(raw_count * scaling_factor))
                    percentage = round((estimated_count / total_reviews) * 100, 1)

                    examples = [r["review_text"] for r in matching_rows[:2]]
                    evidence_ids = [r["id"] for r in matching_rows[:10]]

                    cons.append(
                        ProConTheme(
                            theme=cluster["theme"],
                            review_count=estimated_count,
                            percentage=percentage,
                            example_reviews=examples,
                            evidence_review_ids=evidence_ids,
                        )
                    )

            # Sort Cons by review count descending
            cons.sort(key=lambda x: x.review_count, reverse=True)
            cons = cons[:4]

            # Fallback when no theme matched. Only real aggregated counts are
            # reported; no evidence quote is invented (Gate 2, Phase 4) —
            # example_reviews stays empty because no source review supports
            # any specific theme.
            pros_from_fallback = False
            if not pros and pos_count > 0:
                pros_from_fallback = True
                pros.append(
                    ProConTheme(
                        theme="Overall Customer Satisfaction",
                        review_count=pos_count,
                        percentage=round((pos_count / total_reviews) * 100, 1),
                        example_reviews=[],
                        evidence_review_ids=[],
                    )
                )

            cons_from_fallback = False
            if not cons and neg_count > 0:
                cons_from_fallback = True
                cons.append(
                    ProConTheme(
                        theme="General Customer Dissatisfaction",
                        review_count=neg_count,
                        percentage=round((neg_count / total_reviews) * 100, 1),
                        example_reviews=[],
                        evidence_review_ids=[],
                    )
                )

            # Top pros & cons titles
            top_pros = [p.theme for p in pros[:3]]
            top_cons = [c.theme for c in cons[:3]]

            # Sentiment percentages
            sentiment_percentages = {
                "positive": round((pos_count / total_reviews) * 100, 1),
                "neutral": round((neu_count / total_reviews) * 100, 1),
                "negative": round((neg_count / total_reviews) * 100, 1),
            }

            # Source-provenance signals: only statements backed by the actual
            # computation are reported (Gate 2, Phase 4). Fabricated
            # detection/correlation claims are deliberately absent.
            authenticity_signals = [
                f"Theme keyword analysis sampled {analyzed_pool_size:,} of {total_reviews:,} available product reviews; mention counts are projections onto the full pool.",
                f"Average rating: {avg_rating} / 5.0 across {total_reviews:,} dataset reviews.",
                f"Sentiment distribution: {sentiment_percentages['positive']}% positive, {sentiment_percentages['neutral']}% neutral, {sentiment_percentages['negative']}% negative.",
            ]

            summary_parts = [
                f"Based on {total_reviews:,} customer reviews in the dataset, {product_title} has an average rating of "
                f"{avg_rating} / 5.0 with {sentiment_percentages['positive']}% positive feedback. "
            ]
            if top_pros:
                if pros_from_fallback:
                    summary_parts.append(
                        f"No recurring positive themes were matched in the sampled reviews; "
                        f"overall sentiment aggregates to {', '.join(top_pros)}. "
                    )
                else:
                    summary_parts.append(
                        f"The most frequently matched positive themes are {', '.join(top_pros)}. "
                    )
            else:
                summary_parts.append(
                    "No recurring positive themes were matched in the sampled reviews. "
                )
            if top_cons:
                if cons_from_fallback:
                    summary_parts.append(
                        f"No recurring negative themes were matched in the sampled reviews; "
                        f"overall sentiment aggregates to {', '.join(top_cons)}."
                    )
                else:
                    summary_parts.append(
                        f"The most frequently matched negative themes are {', '.join(top_cons)}."
                    )
            else:
                summary_parts.append(
                    "No recurring negative themes were matched in the sampled reviews."
                )
            summary_text = "".join(summary_parts)

            return ProsConsAnalysisResponse(
                product_id=str(product_id),
                product_title=product_title,
                # Gate 2 (Phase 4): the number of reviews ACTUALLY analyzed
                # (the sampled pool), which may be far smaller than the
                # available review pool reported in review_volume.
                total_analyzed_reviews=len(sample_rows),
                pros=pros,
                cons=cons,
                summary=summary_text,
                top_pros=top_pros,
                top_cons=top_cons,
                review_volume=total_reviews,
                average_rating=avg_rating,
                sentiment_percentages=sentiment_percentages,
                authenticity_signals=authenticity_signals,
                source_label="Derived strictly from actual dataset reviews",
            )
        finally:
            conn.close()

    def get_theme_reviews(
        self, product_id: str, theme: str, sentiment: Optional[str] = None, limit: int = 50
    ) -> List[ReviewItem]:
        if not ecommerce_db_service.is_ready():
            return []

        # Find keywords for this theme
        keywords = []
        for p in PRO_THEME_PATTERNS + CON_THEME_PATTERNS:
            if p["theme"].lower() == theme.lower():
                keywords = p["keywords"]
                break

        conn = ecommerce_db_service._get_connection()
        try:
            cursor = conn.cursor()

            if keywords:
                # Build SQL query with keyword OR clauses
                like_clauses = " OR ".join(["review_text LIKE ?" for _ in keywords])
                params = [str(product_id)] + [f"%{kw}%" for kw in keywords]

                query = f"""
                    SELECT id, product_id, product_title, category, review_text, rating, sentiment
                    FROM reviews
                    WHERE product_id = ? AND ({like_clauses})
                """
                if sentiment:
                    query += " AND LOWER(sentiment) = ?"
                    params.append(sentiment.lower().strip())

                query += " LIMIT ?;"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
            else:
                cursor.execute("""
                    SELECT id, product_id, product_title, category, review_text, rating, sentiment
                    FROM reviews
                    WHERE product_id = ?
                    LIMIT ?;
                """, (str(product_id), limit))
                rows = cursor.fetchall()

            return [
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
        finally:
            conn.close()


pros_cons_service = ProsConsService()
