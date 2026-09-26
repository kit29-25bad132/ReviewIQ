from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

# V2-P8: deterministic, application-computed evidence-support levels for an
# aspect. These are NEVER inferred, scored, or emitted by the model — the
# grounding stage assigns them from application-known facts. Not a probability
# and not a calibrated confidence score.
AspectSupport = Literal["strong", "moderate", "weak"]

_SUPPORT_VALUES = ("strong", "moderate", "weak")


class ReviewRequest(BaseModel):
    """Incoming request payload containing customer review text."""
    review: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The customer review text to analyze (1 to 5000 characters)"
    )

    @field_validator("review")
    @classmethod
    def strip_and_validate_review(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Review text cannot be empty or whitespace only.")
        return trimmed


class PointEvidence(BaseModel):
    """A single pros/cons claim paired with its supporting evidence text."""
    point: str = Field(
        ...,
        description="Concise positive (pro) or negative (con) point"
    )
    evidence: str = Field(
        ...,
        description="Supporting text for the point (Phase 2 will verify it against the review)"
    )


class AspectSentiment(BaseModel):
    """A single aspect-level sentiment with supporting evidence text.

    V2-P8: ``support`` is an OPTIONAL, application-computed evidence-support
    signal. The model must never be trusted to supply it: ``grounding_service``
    re-computes and overwrites it deterministically after evidence grounding.
    It stays ``None`` only for analyses that bypass the grounding stage (e.g.
    raw contract validation), so pre-P8 payloads and existing clients keep
    validating unchanged.
    """
    aspect: str = Field(
        ...,
        description="Product aspect/attribute discussed in the review (e.g. 'battery')"
    )
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = Field(
        ...,
        description="Sentiment expressed about this aspect"
    )
    evidence: str = Field(
        ...,
        description="Supporting text for the aspect sentiment"
    )
    support: Optional[AspectSupport] = Field(
        default=None,
        description=(
            "Deterministic evidence-support level computed by the application "
            "after grounding (never a model confidence or probability): "
            "'strong' = evidence is a verbatim substring of the original review "
            "and mentions the aspect; 'moderate' = evidence is grounded only "
            "after normalization and mentions the aspect; 'weak' = grounded but "
            "does not mention the aspect. Null when grounding has not run."
        ),
    )

    @field_validator("support", mode="before")
    @classmethod
    def normalize_support_input(cls, v: Any) -> Optional[str]:
        """Accept only recognized support values; discard anything else.

        The value is authoritative only when assigned by the grounding stage.
        Normalizing here prevents an unexpected model-emitted value from
        turning a valid analysis into a validation failure (which would waste
        a fallback attempt), while preserving legitimate round-trips of an
        already-grounded analysis.
        """
        if isinstance(v, str):
            candidate = v.strip().lower()
            if candidate in _SUPPORT_VALUES:
                return candidate
        return None


class ReviewAnalysis(BaseModel):
    """Canonical V1 structured review analysis output (Phase 1 contract)."""
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = Field(
        ...,
        description="Overall sentiment: 'positive', 'negative', 'neutral', or 'mixed'"
    )
    rating: Optional[int] = Field(
        ...,
        ge=1,
        le=5,
        description="Star rating from 1 to 5, or null when no reliable rating is available. "
                    "Invalid values are rejected (never clamped or rounded)."
    )
    rating_source: Literal["explicit", "inferred", "not_found"] = Field(
        ...,
        description="Where the rating came from: 'explicit' (stated in review), "
                    "'inferred' (derived from sentiment), or 'not_found'"
    )
    summary: str = Field(
        ...,
        description="Concise summary highlighting the main points of the customer review"
    )
    aspects: List[AspectSentiment] = Field(
        default_factory=list,
        description="Aspect-based sentiment analysis: each discussed aspect with its own sentiment and supporting evidence from the review"
    )
    pros: List[PointEvidence] = Field(
        default_factory=list,
        description="Positive points with supporting evidence"
    )
    cons: List[PointEvidence] = Field(
        default_factory=list,
        description="Negative points with supporting evidence"
    )

    @field_validator("sentiment", mode="before")
    @classmethod
    def normalize_sentiment(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip().lower()
            if val in ["positive", "negative", "neutral", "mixed"]:
                return val
        return v

    @model_validator(mode="after")
    def validate_rating_source_consistency(self) -> "ReviewAnalysis":
        if self.rating is None and self.rating_source != "not_found":
            raise ValueError(
                "rating_source must be 'not_found' when rating is null"
            )
        if self.rating is not None and self.rating_source == "not_found":
            raise ValueError(
                "rating_source 'not_found' requires rating to be null"
            )
        return self


class AnalyzeReviewResponse(BaseModel):
    """Standardized API response structure."""
    success: bool
    data: Optional[ReviewAnalysis] = None
    error: Optional[str] = None
