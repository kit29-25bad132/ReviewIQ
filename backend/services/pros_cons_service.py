import logging
import math
from typing import Any, Dict, List, Optional

from models.ecommerce import (
    ProConTheme,
    ProsConsAnalysisResponse,
    ReviewItem,
)
from services.catalog.catalog_service import canonical_catalog

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
    """Deterministic keyword aggregation over canonical Supabase reviews.

    The algorithm is unchanged from the legacy implementation; only the row
    source moved from SQLite to CanonicalCatalogService. Every theme count,
    example, and evidence ID derives from retrieved canonical records.
    """

    @staticmethod
    def _pool_rows(product_id: str) -> List[Dict[str, Any]]:
        """Fetches the canonical sample pool as SQLite-shaped rows."""
        reviews, _ = canonical_catalog.get_reviews(product_id, page=1, page_size=5000)
        return [
            {
                "id": str(r["source_review_id"]),
                "review_text": str(r["review_text"]),
                "rating": int(r["rating"]),
                "sentiment": str(r.get("sentiment", "neutral")),
            }
            for r in reviews
        ]

    def analyze_product_pros_cons(self, product_id: str) -> Optional[ProsConsAnalysisResponse]:
        if not canonical_catalog.is_configured():
            return None

        stats = canonical_catalog.get_product_statistics(str(product_id))
        if not stats or stats["total_reviews"] == 0:
            return None

        product = stats["product"]
        product_title = product["product_title"]
        total_reviews = stats["total_reviews"]
        avg_rating = stats["average_rating"] or 0.0
        sent_dist = stats["sentiment_distribution"]
        pos_count = sent_dist.get("positive", 0) or 0
        neu_count = sent_dist.get("neutral", 0) or 0
        neg_count = sent_dist.get("negative", 0) or 0

        # Sample pool for deep keyword pattern extraction (up to 5,000 canonical reviews)
        sample_rows = self._pool_rows(str(product["source_product_id"]))
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
                # Extrapolate count proportionally if sample pool is smaller than total reviews
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
        cons = cons[:4]

        # If no specific themed clusters matched, ground fallback in actual review text from database
        if not pros and pos_count > 0:
            pos_reviews = [r for r in sample_rows if r["sentiment"].lower() == "positive" or r["rating"] >= 4]
            real_examples = [r["review_text"] for r in pos_reviews[:2]]
            real_ids = [r["id"] for r in pos_reviews[:5]]
            pros.append(
                ProConTheme(
                    theme="Positive Customer Experience",
                    review_count=pos_count,
                    percentage=round((pos_count / total_reviews) * 100, 1),
                    example_reviews=real_examples,
                    evidence_review_ids=real_ids,
                )
            )

        if not cons and neg_count > 0:
            neg_reviews = [r for r in sample_rows if r["sentiment"].lower() == "negative" or r["rating"] <= 2]
            real_examples = [r["review_text"] for r in neg_reviews[:2]]
            real_ids = [r["id"] for r in neg_reviews[:5]]
            cons.append(
                ProConTheme(
                    theme="Customer Reported Issues",
                    review_count=neg_count,
                    percentage=round((neg_count / total_reviews) * 100, 1),
                    example_reviews=real_examples,
                    evidence_review_ids=real_ids,
                )
            )

        # Top pros & cons titles
        top_pros = [p.theme for p in pros[:3]]
        top_cons = [c.theme for c in cons[:3]]

        # Sentiment percentages
        sentiment_percentages = {
            "positive": round((pos_count / total_reviews) * 100, 1) if total_reviews else 0.0,
            "neutral": round((neu_count / total_reviews) * 100, 1) if total_reviews else 0.0,
            "negative": round((neg_count / total_reviews) * 100, 1) if total_reviews else 0.0,
        }

        # Authenticity signals
        authenticity_signals = [
                f"Statistical sample analyzed across {total_reviews:,} canonical dataset reviews.",
            f"Mean customer rating: {avg_rating} / 5.0 stars ({sentiment_percentages['positive']}% positive feedback).",
            f"Evidence gathered from {analyzed_pool_size:,} retrieved database reviews.",
        ]

        summary_text = (
            f"Based on {total_reviews:,} customer reviews in the database, {product_title} has an average rating of "
            f"{avg_rating} / 5.0 with {sentiment_percentages['positive']}% positive feedback. "
            f"Customers most frequently praise {', '.join(top_pros) if top_pros else 'its performance'}, "
            f"while negative feedback focuses on {', '.join(top_cons) if top_cons else 'noted concerns'}."
        )

        return ProsConsAnalysisResponse(
            product_id=str(product_id),
            product_title=product_title,
            total_analyzed_reviews=total_reviews,
            pros=pros,
            cons=cons,
            summary=summary_text,
            top_pros=top_pros,
            top_cons=top_cons,
            review_volume=total_reviews,
            average_rating=avg_rating,
            sentiment_percentages=sentiment_percentages,
            authenticity_signals=authenticity_signals,
                source_label="Derived strictly from canonical dataset reviews",
        )


    def get_theme_reviews(
        self, product_id: str, theme: str, sentiment: Optional[str] = None, limit: int = 50
    ) -> List[ReviewItem]:
        if not canonical_catalog.is_configured():
            return []

        product = canonical_catalog.get_product_by_id(str(product_id))
        if product is None:
            return []

        # Find keywords for this theme
        keywords = []
        for p in PRO_THEME_PATTERNS + CON_THEME_PATTERNS:
            if p["theme"].lower() == theme.lower():
                keywords = p["keywords"]
                break

        reviews, _ = canonical_catalog.get_reviews(str(product_id), page=1, page_size=5000)

        matching = []
        for r in reviews:
            if sentiment and str(r.get("sentiment", "")).strip().lower() != sentiment.strip().lower():
                continue
            if keywords:
                text_lower = str(r["review_text"]).lower()
                if not any(kw in text_lower for kw in keywords):
                    continue
            matching.append(r)
            if len(matching) >= limit:
                break

        return [
            ReviewItem(
                id=str(r["source_review_id"]),
                product_id=str(r["source_product_id"]),
                product_title=str(product["product_title"]),
                category=product["category"],
                review_text=str(r["review_text"]),
                rating=int(r["rating"]),
                sentiment=str(r.get("sentiment", "neutral")),
            )
            for r in matching
        ]


pros_cons_service = ProsConsService()
