"""Phase 5 API contracts for real product intelligence.

These models are the enforced boundary for Phase 5. They live here (rather than
inside ``models.ecommerce``) so the legacy analysis shape can be migrated onto
them and then removed, instead of being broken in place.

Enforcement is deliberate and strict:
* a :class:`ClaimWithEvidence` cannot exist with fewer than one evidence item,
* an :class:`AspectResult` cannot exist with a mention count below 1,
* :class:`ProductStatistics` distributions must be exhaustive and must sum to
  ``total_reviews`` — so a hardcoded or drifted number cannot validate,
* a failure returns an :class:`AnalysisErrorResponse` (never a partial
  payload), via :func:`validate_analysis_response`.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Set

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from models.ecommerce import ReviewItem

logger = logging.getLogger(__name__)

#: Exactly the canonical source this whole phase reads from.
DATA_SOURCE_SUPABASE = "supabase"

#: The only rating keys a valid distribution may contain.
RATING_KEYS = (1, 2, 3, 4, 5)

#: The only sentiment buckets a valid distribution may contain.
SENTIMENT_KEYS = ("positive", "neutral", "negative")

#: Summary returned when there is nothing real to summarize (5G).
INSUFFICIENT_REVIEWS_SUMMARY = "Insufficient reviews"


class ReviewPage(BaseModel):
    """One page of real canonical reviews (5E).

    ``total_count`` and ``page_size`` are the canonical 5E field names.
    ``total`` and ``limit`` are legacy aliases that are still populated so
    existing clients keep working; they are removed in 5H once the frontend
    has been rewired.
    """

    items: List[ReviewItem] = Field(default_factory=list)
    total_count: int
    page: int
    page_size: int
    total_pages: int
    # Deprecated legacy aliases (removed in 5H).
    total: int = 0
    limit: int = 0


class DateRange(BaseModel):
    """Earliest and latest review dates for a product (ISO-8601 strings)."""

    earliest: Optional[str] = None
    latest: Optional[str] = None

    @model_validator(mode="after")
    def validate_order(self) -> "DateRange":
        if self.earliest and self.latest and self.earliest > self.latest:
            raise ValueError("date_range.earliest must not be after latest")
        return self


class EvidenceItem(BaseModel):
    """A single traceable citation: a real review id plus a verbatim excerpt."""

    review_id: str = Field(..., min_length=1)
    excerpt: str = Field(..., min_length=1)


class ClaimWithEvidence(BaseModel):
    """A pro/con claim that is only valid when backed by real evidence."""

    claim: str = Field(..., min_length=1)
    evidence: List[EvidenceItem] = Field(
        ...,
        min_length=1,
        description="At least one traceable review citation is mandatory.",
    )
    support_count: int = Field(
        ...,
        ge=1,
        description="How many reviews support this claim (>= 1 because evidence is required).",
    )


class AspectResult(BaseModel):
    """One recurring product aspect/theme with its own sentiment and quote."""

    aspect_name: str = Field(..., min_length=1)
    sentiment: Literal["positive", "negative", "mixed"]
    mention_count: int = Field(..., ge=1)
    representative_quote: EvidenceItem


class ProductStatistics(BaseModel):
    """Database-derived statistics (5A output) as an enforced contract."""

    total_reviews: int = Field(..., ge=0)
    average_rating: float = Field(..., ge=0.0, le=5.0)
    rating_distribution: Dict[int, int]
    sentiment_distribution: Dict[str, int]
    verified_purchase_pct: float = Field(..., ge=0.0, le=100.0)
    date_range: DateRange

    @field_validator("average_rating")
    @classmethod
    def validate_one_decimal_place(cls, value: float) -> float:
        """The contract requires 1dp; 5A rounds this in SQL, never in Python."""
        if abs(value - round(value, 1)) > 1e-9:
            raise ValueError("average_rating must be rounded to 1 decimal place")
        return value

    @model_validator(mode="after")
    def validate_distributions(self) -> "ProductStatistics":
        if sorted(self.rating_distribution.keys()) != list(RATING_KEYS):
            raise ValueError(
                f"rating_distribution must contain exactly the keys {list(RATING_KEYS)}"
            )
        if any(count < 0 for count in self.rating_distribution.values()):
            raise ValueError("rating_distribution counts cannot be negative")
        rating_sum = sum(self.rating_distribution.values())
        if rating_sum != self.total_reviews:
            raise ValueError(
                f"rating_distribution sums to {rating_sum} but total_reviews is "
                f"{self.total_reviews}"
            )

        if sorted(self.sentiment_distribution.keys()) != sorted(SENTIMENT_KEYS):
            raise ValueError(
                "sentiment_distribution must contain exactly the keys "
                f"{list(SENTIMENT_KEYS)}"
            )
        if any(count < 0 for count in self.sentiment_distribution.values()):
            raise ValueError("sentiment_distribution counts cannot be negative")
        sentiment_sum = sum(self.sentiment_distribution.values())
        if sentiment_sum != self.total_reviews:
            raise ValueError(
                f"sentiment_distribution sums to {sentiment_sum} but total_reviews "
                f"is {self.total_reviews}"
            )
        return self


class ProductAnalysisResponse(BaseModel):
    """The complete Phase 5 product intelligence payload."""

    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    statistics: ProductStatistics
    aspects: List[AspectResult] = Field(default_factory=list)
    pros: List[ClaimWithEvidence] = Field(default_factory=list)
    cons: List[ClaimWithEvidence] = Field(default_factory=list)
    summary: str
    best_for: str
    data_source: Literal["supabase"]
    review_count_used: int = Field(..., ge=0)
    generated_at: datetime
    # Additive 5G flags (not listed in the 5F field list, but required by 5G).
    low_review_count: bool = False
    ai_unavailable: bool = False

    @model_validator(mode="after")
    def validate_invariants(self) -> "ProductAnalysisResponse":
        if self.review_count_used > self.statistics.total_reviews:
            raise ValueError(
                "review_count_used cannot exceed statistics.total_reviews"
            )
        if self.ai_unavailable and (self.aspects or self.pros or self.cons):
            raise ValueError(
                "ai_unavailable responses must carry empty aspects/pros/cons"
            )
        return self


class AnalysisErrorResponse(BaseModel):
    """Structured failure returned instead of a partially-invalid payload."""

    code: Literal[
        "validation_error",
        "product_not_found",
        "insufficient_reviews",
        "ai_unavailable",
    ]
    error: str
    detail: Optional[str] = None


def filter_evidence_backed_claims(
    claims: List[ClaimWithEvidence],
    valid_review_ids: Set[str],
) -> List[ClaimWithEvidence]:
    """Drop claims whose evidence does not resolve to a real review.

    A claim survives only if every one of its citations exists in
    ``valid_review_ids``. This is the enforcement point for "if a claim has no
    traceable evidence, it must be dropped" (5C): nothing invented can reach
    the response.
    """
    kept: List[ClaimWithEvidence] = []
    for claim in claims:
        if not claim.evidence:
            continue
        if all(item.review_id in valid_review_ids for item in claim.evidence):
            kept.append(claim)
        else:
            logger.warning(
                "Dropping claim with untraceable evidence: %s", claim.claim
            )
    return kept


def validate_analysis_response(
    payload: Any,
) -> "ProductAnalysisResponse | AnalysisErrorResponse":
    """Validate a candidate payload, never raising at the API boundary.

    Returns the validated response on success, or a structured
    :class:`AnalysisErrorResponse` on failure — so the frontend never receives
    a partially-invalid payload and the route never has to 500.
    """
    try:
        return ProductAnalysisResponse.model_validate(payload)
    except ValidationError as exc:
        logger.error("Product analysis payload failed validation: %s", exc)
        return AnalysisErrorResponse(
            code="validation_error",
            error="The product analysis response failed validation and was not returned.",
            detail=f"{exc.error_count()} validation error(s).",
        )
