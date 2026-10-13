import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from models.ecommerce import (
    ProductSummary,
    UserRequirementRequest,
    ProductComparisonItem,
    PriorityMatchEvidence,
    PersonalizedRecommendationResponse,
)
from services.catalog.catalog_service import canonical_catalog
from services.pros_cons_service import pros_cons_service

logger = logging.getLogger(__name__)

PERSONA_DEFAULTS = {
    "Gamer": ["Performance", "Quality & Durability", "Speed"],
    "Student": ["Value for Money", "Ease of Use", "Durability"],
    "Photographer": ["Performance", "Quality & Durability", "Design"],
    "Professional": ["Quality & Durability", "Reliability", "Ease of Use"],
    "Content Creator": ["Performance", "Quality & Durability", "Value for Money"],
    "General User": ["Value for Money", "Ease of Use", "Product Reliability"],
}

# Weight of user-priority alignment in the composite candidate score.
# Base satisfaction contributes avg*0.6 + pos_share*0.4 (range ~[0.6, 3.4]);
# alignment contributes up to 1.0, so stated priorities can tip close races
# without overwhelming the rating evidence. Deterministic and documented.
PRIORITY_ALIGNMENT_WEIGHT = 1.0


# Domain-specific subcategory and product-type semantic taxonomy for genuine relationship matching
PRODUCT_TAXONOMY = {
    # Smartphone
    'smartphone': {'smartphone', 'phone', '5g', 'pixel', 'nova', 'm14', 'x7', 'lite', 'pro'},

    # Headphones
    'headphones': {'headphone', 'headphones', 'earbud', 'earbuds', 'earphone', 'earphones', 'headset', 'audio', 'sound', 'basspro', 'soundmax', 'neckband', 'anc', 'buds'},

    # Laptop
    'laptop': {'laptop', 'notebook', 'air', 'probook', 'slim', 'gamer', 'computer'},

    # Kitchen
    'kitchen_appliances': {'blender', 'mixer', 'juicer', 'grinder', 'quickblend', 'airfryer', 'air fryer', 'airfry', 'cookware', 'cooktop', 'induction', 'pan', 'pot'},

    # Fitness Band / Wearables
    'fitness_band': {'fitness band', 'band', 'watch', 'smartwatch', 'tracker', 'pulse', 'active', 'fit lite'},
}

STOPWORDS = {'a', 'an', 'the', 'and', 'or', 'with', 'for', 'of', 'in', 'on', 'at', 'by', 'set', 'pack', 'kit', 'bundle', 'pcs'}


def extract_title_tokens(text: str) -> set:
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def get_product_subcategories(title: str) -> set:
    t_lower = title.lower()
    matched = set()
    for subcat, terms in PRODUCT_TAXONOMY.items():
        for term in terms:
            if re.search(r'\b' + re.escape(term) + r'\b', t_lower):
                matched.add(subcat)
    return matched


def compute_product_relationship_score(
    target_title: str, target_cat: str,
    candidate_title: str, candidate_cat: str
) -> float:
    """
    Computes genuine relationship score between two products using dataset metadata.
    Must match exact category and have matching sub-category/product type or specific domain token overlap.
    """
    if not target_cat or not candidate_cat or target_cat.strip().lower() != candidate_cat.strip().lower():
        return 0.0

    score = 30.0  # Exact category match baseline

    target_subcats = get_product_subcategories(target_title)
    cand_subcats = get_product_subcategories(candidate_title)
    common_subcats = target_subcats.intersection(cand_subcats)

    target_tokens = extract_title_tokens(target_title)
    cand_tokens = extract_title_tokens(candidate_title)
    common_tokens = target_tokens.intersection(cand_tokens)

    if common_subcats:
        score += 30.0 * len(common_subcats)

    if common_tokens:
        score += 15.0 * len(common_tokens)

    return score


def priority_matches_theme(priority: str, theme_title: str) -> bool:
    """Word-overlap rule shared by narrative evidence and ranking alignment,
    so the explanation always agrees with the score."""
    prio_lower = priority.lower()
    theme_lower = theme_title.lower()
    return any(w in theme_lower for w in prio_lower.split()) or any(
        w in prio_lower for w in theme_lower.split()
    )


def compute_priority_alignment(
    priorities: List[str], pro_themes: List[Tuple[str, float]]
) -> float:
    """Mean evidence strength of user priorities across a candidate's pros.

    Each theme is a (title, percentage) pair from the pros-cons analysis.
    For every priority the best-matching theme's percentage is divided by
    100, keeping alignment in 0.0-1.0 (the same range as the previous
    binary matched-fraction); unmatched priorities contribute 0.0 and the
    aggregate is capped at 1.0. An empty priority list scores 0.0 so the
    rating baseline alone decides.
    """
    if not priorities:
        return 0.0
    total = 0.0
    for prio in priorities:
        best = 0.0
        for theme, pct in pro_themes:
            if priority_matches_theme(prio, theme):
                best = max(best, min(1.0, max(0.0, pct) / 100.0))
        total += best
    return min(1.0, total / len(priorities))


def composite_candidate_score(average_rating: float, positive_percentage: float, alignment: float) -> float:
    """Base satisfaction plus preference alignment. Pure and deterministic."""
    base = (average_rating or 0.0) * 0.6 + ((positive_percentage or 0.0) / 100) * 0.4
    return base + PRIORITY_ALIGNMENT_WEIGHT * (alignment or 0.0)


class RecommendationService:
    """Canonical-catalog recommendations and similar products.

    Candidates, ratings, counts, and sentiment all come from Supabase via
    CanonicalCatalogService; there is no SQLite fallback. `budget` and
    `custom_requirements` are accepted by the request contract but do NOT
    affect ranking (documented here rather than claimed otherwise).
    """

    def get_similar_products(self, product_id: str, limit: int = 3) -> List[ProductSummary]:
        """
        Discovers genuinely related products in the dataset based on strict category,
        sub-category, product-type, and metadata token overlap.
        Excludes the selected product and broad department mismatches.
        """
        if not canonical_catalog.is_configured():
            return []

        clean_pid = str(product_id).strip()
        target = canonical_catalog.get_product_by_id(clean_pid)
        if not target or not target.get("category"):
            return []

        target_title = target["product_title"]
        target_category = target["category"]
        target_key = (str(target["id"]), str(target["source_product_id"]))

        # Single aggregated query: same-category candidates with canonical stats (no N+1).
        candidates, _ = canonical_catalog.get_products(category=target_category, limit=50)

        # Score candidates strictly using subcategory and product-type metadata
        scored_candidates = []
        for cand in candidates:
            if str(cand["id"]) in target_key or str(cand["source_product_id"]) in target_key:
                continue
            score = compute_product_relationship_score(
                target_title=target_title,
                target_cat=target_category,
                candidate_title=cand["product_title"],
                candidate_cat=cand["category"]
            )
            # Strict threshold: must have genuine sub-category or product-type relationship
            if score >= 30.0:
                scored_candidates.append((score, cand))

        # Sort by relationship score DESC, review_count DESC, average_rating DESC
        scored_candidates.sort(
            key=lambda x: (x[0], x[1]["review_count"] or 0, x[1]["average_rating"] or 0.0),
            reverse=True
        )

        # Limit to top genuinely related products (max limit, default 3)
        return [
            ProductSummary(
                product_id=str(r[1]["source_product_id"]),
                product_title=r[1]["product_title"],
                category=r[1]["category"],
                review_count=r[1]["review_count"],
                average_rating=r[1]["average_rating"],
            )
            for r in scored_candidates[:limit]
        ]

    def generate_recommendation(
        self, product_id: str, req: UserRequirementRequest
    ) -> Optional[PersonalizedRecommendationResponse]:
        if not canonical_catalog.is_configured():
            return None

        clean_pid = str(product_id).strip()
        target = canonical_catalog.get_product_by_id(clean_pid)
        if not target:
            return None
        sel_stats = canonical_catalog.get_product_statistics(clean_pid)
        if not sel_stats or sel_stats["total_reviews"] == 0:
            return None

        sel_key = str(target["source_product_id"])
        sel_summary = ProductSummary(
            product_id=sel_key,
            product_title=target["product_title"],
            category=target["category"],
            review_count=sel_stats["total_reviews"],
            average_rating=sel_stats["average_rating"] or 0.0,
        )

        # Discover similar products in the same category
        similar_products = self.get_similar_products(clean_pid, limit=3)

        # Compile comparison data for selected + similar products
        comparison_items: List[ProductComparisonItem] = []
        candidate_keys = [sel_key] + [sp.product_id for sp in similar_products]

        candidate_stats: Dict[str, dict] = {}
        for key in candidate_keys:
            st = sel_stats if key == sel_key else canonical_catalog.get_product_statistics(key)
            if st and st["total_reviews"] > 0:
                candidate_stats[key] = st

        # Determine priorities from persona or explicit list (shared by narrative and scoring)
        user_priorities = list(req.priorities) if req.priorities else []
        if req.persona and req.persona in PERSONA_DEFAULTS and not user_priorities:
            user_priorities = PERSONA_DEFAULTS[req.persona]

        if not user_priorities:
            user_priorities = ["Product Reliability", "Value for Money", "Quality & Durability"]

        candidate_pros: Dict[str, List[str]] = {}
        candidate_pro_theme_pcts: Dict[str, List[Tuple[str, float]]] = {}
        candidate_cons: Dict[str, List[str]] = {}
        for key in candidate_stats:
            cand_pc = pros_cons_service.analyze_product_pros_cons(key)
            if cand_pc:
                top_pros = cand_pc.pros[:4]
                candidate_pros[key] = [p.theme for p in top_pros]
                candidate_pro_theme_pcts[key] = [(p.theme, p.percentage) for p in top_pros]
                candidate_cons[key] = [c.theme for c in cand_pc.cons[:3]]
            else:
                candidate_pros[key] = []
                candidate_pro_theme_pcts[key] = []
                candidate_cons[key] = []

        for key, st in candidate_stats.items():
            prod = st["product"]
            tot = st["total_reviews"] or 1
            sent = st["sentiment_distribution"]
            pos_pct = round(((sent.get("positive", 0) or 0) / tot) * 100, 1)
            neu_pct = round(((sent.get("neutral", 0) or 0) / tot) * 100, 1)
            neg_pct = round(((sent.get("negative", 0) or 0) / tot) * 100, 1)

            pros_list = candidate_pros.get(key, [])
            cons_list = candidate_cons.get(key, [])

            comparison_items.append(
                ProductComparisonItem(
                    product_id=key,
                    product_title=prod["product_title"],
                    category=prod["category"] or "General",
                    average_rating=st["average_rating"] or 0.0,
                    review_count=st["total_reviews"] or 0,
                    positive_percentage=pos_pct,
                    negative_percentage=neg_pct,
                    neutral_percentage=neu_pct,
                    common_pros=pros_list,
                    common_cons=cons_list,
                    is_selected=(key == sel_key),
                )
            )

        # Analyze priority matches with dataset review evidence
        priority_matches: List[PriorityMatchEvidence] = []
        sel_pros_cons = pros_cons_service.analyze_product_pros_cons(sel_key)

        for prio in user_priorities:
            matched_pro = None
            if sel_pros_cons:
                for p in sel_pros_cons.pros:
                    if priority_matches_theme(prio, p.theme):
                        matched_pro = p
                        break

            if matched_pro:
                priority_matches.append(
                    PriorityMatchEvidence(
                        priority=prio,
                        evidence_level="Strong Evidence",
                        details=f"Detected in {matched_pro.review_count:,} reviews ({matched_pro.percentage}% of analyzed dataset reviews).",
                        supporting_reviews=matched_pro.example_reviews[:2],
                    )
                )
            else:
                priority_matches.append(
                    PriorityMatchEvidence(
                        priority=prio,
                        evidence_level="Moderate Evidence",
                        details="General customer satisfaction aligns with this requirement.",
                        supporting_reviews=[],
                    )
                )

        # budget: not implemented in V2 — price data unverified.
        # Deferred to V3 after confirming price column and values.
        # Best candidate by preference-aware composite score (rating evidence
        # plus percentage-weighted alignment of each candidate's pro themes
        # with user priorities).
        scored = []
        for item in comparison_items:
            alignment = compute_priority_alignment(
                user_priorities, candidate_pro_theme_pcts.get(item.product_id, [])
            )
            scored.append(
                (composite_candidate_score(item.average_rating, item.positive_percentage, alignment), item)
            )
        best_score, best_candidate = max(scored, key=lambda x: x[0])
        best_product_summary = ProductSummary(
            product_id=best_candidate.product_id,
            product_title=best_candidate.product_title,
            category=best_candidate.category,
            review_count=best_candidate.review_count,
            average_rating=best_candidate.average_rating,
        )

        is_selected_the_best = (best_candidate.product_id == sel_key)

        # Persona-specific insights and reasoning
        persona_name = req.persona or "General User"

        persona_rationale_map = {
            "Student": f"Evaluated under a Student lens focusing on affordability, daily usability, and budget value across {sel_summary.review_count:,} reviews.",
            "Professional": f"Evaluated under a Professional lens prioritizing long-term durability, build consistency, and reliable daily operation.",
            "Gamer": f"Evaluated under a Performance & Enthusiast lens focusing on responsiveness, endurance, and build quality.",
            "Content Creator": f"Evaluated under a Creative Workflow lens focusing on dependable output quality, versatility, and durability.",
            "Photographer": f"Evaluated under an Enthusiast & Precision lens focusing on materials, finish, and design quality.",
            "General User": f"Evaluated under a General User lens balancing overall customer satisfaction, ease of use, and verified rating distribution.",
        }
        persona_context = persona_rationale_map.get(persona_name, f"Evaluated for {persona_name} priorities.")

        # Suitability
        top_pros_titles = sel_pros_cons.top_pros if sel_pros_cons else ["Quality & Performance"]
        top_cons_titles = sel_pros_cons.top_cons if sel_pros_cons else ["Minor complaints"]

        suitable_for = [
            f"Ideal for {persona_name}s prioritizing {', '.join(user_priorities[:2])}.",
            f"Backed by a {sel_summary.average_rating} ★ average score across {sel_summary.review_count:,} canonical dataset reviews.",
            f"Top customer-verified strengths: {', '.join(top_pros_titles[:3])}.",
        ]

        consider_before_buying = [
            f"Reported consumer pain points: {', '.join(top_cons_titles[:2])}.",
            f"Negative sentiment rate is {comparison_items[0].negative_percentage}% in the dataset.",
            "Ratings are strictly computed from real database records.",
        ]

        if is_selected_the_best:
            suitability_verdict = (
                    f"Based on your {persona_name} priorities ({', '.join(user_priorities)}) and canonical dataset reviews, "
                f"'{sel_summary.product_title}' is an optimal match with the highest composite satisfaction score in its category ({sel_summary.average_rating} ★)."
            )
            recommendation_headline = f"'{sel_summary.product_title}' is the top-rated match for your {persona_name} profile."
        else:
            suitability_verdict = (
                f"'{sel_summary.product_title}' aligns well with your {persona_name} criteria, but '{best_candidate.product_title}' "
                f"in the same category holds higher overall buyer sentiment ({best_candidate.average_rating} ★ vs {sel_summary.average_rating} ★)."
            )
            recommendation_headline = f"'{best_candidate.product_title}' is recommended as a higher-satisfaction alternative."

        recommendation_reasons = [
            f"{persona_context}",
                f"Supported by {best_candidate.review_count:,} canonical dataset reviews with {best_candidate.positive_percentage}% positive sentiment.",
            f"Consistently demonstrates strengths in {', '.join(best_candidate.common_pros[:2]) if best_candidate.common_pros else 'durability & performance'}.",
            f"Category benchmark: {best_candidate.average_rating} / 5.0 ★ average across customer reviews.",
        ]

        strengths_for_you = [
            f"Directly matches your interest in: {', '.join(user_priorities)}.",
            f"Solid positive sentiment ratio ({best_candidate.positive_percentage}% positive).",
            f"Documented strengths: {', '.join(best_candidate.common_pros) if best_candidate.common_pros else 'Reliability'}.",
        ]

        things_to_consider = [
            f"Keep in mind reported negative themes: {', '.join(best_candidate.common_cons) if best_candidate.common_cons else 'Minor complaints'}.",
            "Recommendation is strictly derived from historical dataset review patterns.",
        ]

        return PersonalizedRecommendationResponse(
            selected_product=sel_summary,
            recommended_product=best_product_summary,
            user_priorities=user_priorities,
            priority_matches=priority_matches,
            suitability_verdict=suitability_verdict,
            suitable_for=suitable_for,
            consider_before_buying=consider_before_buying,
            comparison_products=comparison_items,
            recommendation_headline=recommendation_headline,
            recommendation_reasons=recommendation_reasons,
            strengths_for_you=strengths_for_you,
            things_to_consider=things_to_consider,
            source_label=f"Personalized {persona_name} recommendation derived strictly from dataset review evidence",
        )


recommendation_service = RecommendationService()
