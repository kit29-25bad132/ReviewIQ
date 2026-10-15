"""Trustworthiness, Provenance, and Metadata Integrity Checker for ReviewIQ."""

from typing import Any, Dict, List, Set


class TrustworthinessChecker:
    """Validates review trustworthiness, metadata consistency, and provenance coverage."""

    def check(self, rows: List[Dict[str, Any]], valid_product_ids: Set[str]) -> Dict[str, Any]:
        total_records = len(rows)
        if total_records == 0:
            return {
                "total_records": 0,
                "orphan_reviews_count": 0,
                "provenance_coverage_pct": 100.0,
                "contradictory_metadata_count": 0,
                "trustworthiness_score": 100.0,
                "issues": [],
            }

        orphan_count = 0
        missing_provenance_count = 0
        contradictory_count = 0
        issues = []

        for i, row in enumerate(rows):
            pid = str(row.get("product_id", "")).strip()
            rid = str(row.get("review_id", "")).strip()
            rating_val = row.get("rating")
            sentiment_val = str(row.get("sentiment", "")).strip().lower()

            # 1. Orphan check
            if pid not in valid_product_ids:
                orphan_count += 1
                issues.append(f"Orphan review {rid}: product_id '{pid}' does not exist in product universe.")

            # 2. Provenance check (source review identity exists and is traceable)
            if not rid or not pid:
                missing_provenance_count += 1
                issues.append(f"Missing identity/provenance at row index {i}.")

            # 3. Contradictory rating/sentiment check
            try:
                rating = int(float(rating_val))
                if rating == 5 and sentiment_val == "negative":
                    contradictory_count += 1
                    issues.append(f"Contradictory review {rid}: 5-star rating with 'negative' sentiment.")
                elif rating == 1 and sentiment_val == "positive":
                    contradictory_count += 1
                    issues.append(f"Contradictory review {rid}: 1-star rating with 'positive' sentiment.")
            except (ValueError, TypeError):
                pass

        provenance_coverage_pct = round(
            ((total_records - missing_provenance_count) / total_records) * 100.0, 2
        )

        # Calculate composite trustworthiness score
        deductions = (
            (orphan_count * 5.0)
            + (missing_provenance_count * 5.0)
            + (contradictory_count * 0.5)
        )
        trustworthiness_score = max(0.0, round(100.0 - (deductions / total_records * 100.0), 2))

        return {
            "total_records": total_records,
            "orphan_reviews_count": orphan_count,
            "missing_provenance_count": missing_provenance_count,
            "provenance_coverage_pct": provenance_coverage_pct,
            "contradictory_metadata_count": contradictory_count,
            "trustworthiness_score": trustworthiness_score,
            "issues": issues[:10],  # Sample issues
        }


trustworthiness_checker = TrustworthinessChecker()
