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
                # Same documented projection methodology as pros above: the
                # count is an ESTIMATE of full-pool mentions, never a measured
                # full-pool count.
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
        # (Gate 4 flags: when a fallback aggregate stands in for unmatched
        # themes, the summary must say so instead of inventing theme names.)
        pros_from_fallback = False
        if not pros and pos_count > 0:
            pros_from_fallback = True
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

        cons_from_fallback = False
        if not cons and neg_count > 0:
            cons_from_fallback = True
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

        # Source-provenance signals: only statements backed by the actual
        # computation are reported (Gate 2/Gate 4, Phase 4): the sampled size,
        # the available pool, and the fact that mention counts are projections
        # onto that pool. No fabricated detection/correlation claims.
        authenticity_signals = [
            f"Theme keyword analysis sampled {len(sample_rows):,} of {total_reviews:,} available product reviews; mention counts are projections onto the full pool.",
            f"Average rating: {avg_rating} / 5.0 across {total_reviews:,} dataset reviews.",
            f"Sentiment distribution: {sentiment_percentages['positive']}% positive, {sentiment_percentages['neutral']}% neutral, {sentiment_percentages['negative']}% negative.",
        ]

        summary_text = (
            f"Based on {total_reviews:,} customer reviews in the database, {product_title} has an average rating of "
            f"{avg_rating} / 5.0 with {sentiment_percentages['positive']}% positive feedback. "
        )
        # Never invent theme names when no theme matched (Gate 4): report the
        # unmatched state plainly, or name only themes actually matched.
        if top_pros:
            if pros_from_fallback:
                summary_text += (
                    f"No recurring positive themes were matched in the sampled reviews; "
                    f"overall sentiment aggregates to {', '.join(top_pros)}. "
                )
            else:
                summary_text += f"The most frequently matched positive themes are {', '.join(top_pros)}. "
        else:
            summary_text += "No recurring positive themes were matched in the sampled reviews. "
        if top_cons:
            if cons_from_fallback:
                summary_text += (
                    f"No recurring negative themes were matched in the sampled reviews; "
                    f"overall sentiment aggregates to {', '.join(top_cons)}."
                )
            else:
                summary_text += f"The most frequently matched negative themes are {', '.join(top_cons)}."
        else:
            summary_text += "No recurring negative themes were matched in the sampled reviews."

        return ProsConsAnalysisResponse(
            product_id=str(product_id),
            product_title=product_title,
            # Gate 4 (Phase 4): the number of reviews ACTUALLY analyzed (the
            # sampled rows), which may be far smaller than the available review
            # pool reported in review_volume — sample size is never conflated
            # with the full pool.
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
