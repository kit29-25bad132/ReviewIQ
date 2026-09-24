from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


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
    """A single aspect-level sentiment with supporting evidence text."""
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
