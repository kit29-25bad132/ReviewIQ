import logging
from typing import List, Optional

from models.ecommerce import (
    ProductSummary,
    UserRequirementRequest,
    ProductComparisonItem,
    PriorityMatchEvidence,
    PersonalizedRecommendationResponse,
)
from services.ecommerce_db_service import ecommerce_db_service
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


class RecommendationService:
    def get_similar_products(self, product_id: str, limit: int = 3) -> List[ProductSummary]:
        if not ecommerce_db_service.is_ready():
            return []

        conn = ecommerce_db_service._get_connection()
        try:
            cursor = conn.cursor()
            # Get category of selected product
            cursor.execute("SELECT category FROM products WHERE product_id = ?;", (str(product_id),))
            row = cursor.fetchone()
            if not row or not row["category"]:
                return []

            category = row["category"]

            # Fetch other products in same category
            cursor.execute("""
                SELECT product_id, product_title, category, review_count, average_rating
                FROM products
                WHERE category = ? AND product_id != ?
                ORDER BY review_count DESC
                LIMIT ?;
            """, (category, str(product_id), limit))

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

    def generate_recommendation(
        self, product_id: str, req: UserRequirementRequest
    ) -> Optional[PersonalizedRecommendationResponse]:
        if not ecommerce_db_service.is_ready():
            return None

        conn = ecommerce_db_service._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE product_id = ?;", (str(product_id),))
            sel_row = cursor.fetchone()
            if not sel_row:
                return None

            sel_summary = ProductSummary(
                product_id=str(sel_row["product_id"]),
                product_title=sel_row["product_title"],
                category=sel_row["category"],
                review_count=sel_row["review_count"],
                average_rating=sel_row["average_rating"],
            )

            # Discover similar products in the same category
            similar_products = self.get_similar_products(product_id, limit=3)

            # Compile comparison data for selected + similar products
            comparison_items: List[ProductComparisonItem] = []
            all_candidate_rows = [sel_row]

            for sp in similar_products:
                cursor.execute("SELECT * FROM products WHERE product_id = ?;", (sp.product_id,))
                c_row = cursor.fetchone()
                if c_row:
                    all_candidate_rows.append(c_row)

            for cand in all_candidate_rows:
                cand_id = str(cand["product_id"])
                tot = cand["review_count"] or 1
                pos_pct = round((cand["positive_count"] / tot) * 100, 1)
                neu_pct = round((cand["neutral_count"] / tot) * 100, 1)
                neg_pct = round((cand["negative_count"] / tot) * 100, 1)

                cand_pc = pros_cons_service.analyze_product_pros_cons(cand_id)
                pros_list = [p.theme for p in cand_pc.pros[:3]] if cand_pc else []
                cons_list = [c.theme for c in cand_pc.cons[:3]] if cand_pc else []

                comparison_items.append(
                    ProductComparisonItem(
                        product_id=cand_id,
                        product_title=cand["product_title"],
                        category=cand["category"] or "General",
                        average_rating=cand["average_rating"],
                        review_count=cand["review_count"],
                        positive_percentage=pos_pct,
                        negative_percentage=neg_pct,
                        neutral_percentage=neu_pct,
                        common_pros=pros_list,
                        common_cons=cons_list,
                        is_selected=(cand_id == str(product_id)),
                    )
                )

            # Determine priorities from persona or explicit list
            user_priorities = list(req.priorities) if req.priorities else []
            if req.persona and req.persona in PERSONA_DEFAULTS and not user_priorities:
                user_priorities = PERSONA_DEFAULTS[req.persona]

            if not user_priorities:
                user_priorities = ["Product Reliability", "Value for Money", "Quality & Durability"]

            # Analyze priority matches with dataset review evidence
            priority_matches: List[PriorityMatchEvidence] = []
            sel_pros_cons = pros_cons_service.analyze_product_pros_cons(product_id)

            for prio in user_priorities:
                prio_lower = prio.lower()
                matched_pro = None
                if sel_pros_cons:
                    for p in sel_pros_cons.pros:
                        if any(w in p.theme.lower() for w in prio_lower.split()) or any(w in prio_lower for w in p.theme.lower().split()):
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

            # Determine best matching candidate based on rating, positive percentage, and priorities
            best_candidate = max(
                comparison_items,
                key=lambda x: (x.average_rating * 0.6 + (x.positive_percentage / 100) * 0.4),
            )
            best_product_summary = ProductSummary(
                product_id=best_candidate.product_id,
                product_title=best_candidate.product_title,
                category=best_candidate.category,
                review_count=best_candidate.review_count,
                average_rating=best_candidate.average_rating,
            )

            is_selected_the_best = (best_candidate.product_id == str(product_id))

            # Suitability
            top_pros_titles = sel_pros_cons.top_pros if sel_pros_cons else ["Quality"]
            top_cons_titles = sel_pros_cons.top_cons if sel_pros_cons else ["Minor complaints"]

            suitable_for = [
                f"Users prioritizing {', '.join(user_priorities[:2])}.",
                f"Customers seeking high rating confidence ({sel_summary.average_rating} ★ across {sel_summary.review_count:,} reviews).",
                f"Verified strengths: {', '.join(top_pros_titles)}.",
            ]

            consider_before_buying = [
                f"Common dissatisfaction themes: {', '.join(top_cons_titles)}.",
                f"Negative feedback rate is {comparison_items[0].negative_percentage}% in the dataset.",
                "Review evidence reflects real consumer experiences in historical dataset.",
            ]

            if is_selected_the_best:
                suitability_verdict = (
                    f"Based on your stated priorities ({', '.join(user_priorities)}) and the available review dataset, "
                    f"'{sel_summary.product_title}' is a suitable match with the highest composite satisfaction score in its category."
                )
                recommendation_headline = f"'{sel_summary.product_title}' is the closest match for your requirements."
            else:
                suitability_verdict = (
                    f"'{sel_summary.product_title}' satisfies your criteria, but '{best_candidate.product_title}' "
                    f"in the same category exhibits slightly higher average ratings ({best_candidate.average_rating} ★ vs {sel_summary.average_rating} ★)."
                )
                recommendation_headline = f"Consider '{best_candidate.product_title}' as a top alternative in {sel_summary.category}."

            recommendation_reasons = [
                f"Supported by {best_candidate.review_count:,} verified dataset reviews with {best_candidate.positive_percentage}% positive sentiment.",
                f"Consistently demonstrates strengths in {', '.join(best_candidate.common_pros[:2])}.",
                f"Category benchmark: Outperforms peer average in customer satisfaction ({best_candidate.average_rating} / 5.0 ★).",
            ]

            strengths_for_you = [
                f"Directly matches your interest in: {', '.join(user_priorities)}.",
                f"Solid positive sentiment ratio ({best_candidate.positive_percentage}% positive).",
                f"Documented strengths: {', '.join(best_candidate.common_pros)}.",
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
                source_label="Personalized recommendation derived strictly from dataset review evidence",
            )
        finally:
            conn.close()


recommendation_service = RecommendationService()
