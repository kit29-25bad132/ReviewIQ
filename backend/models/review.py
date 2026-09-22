from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


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


class ReviewAnalysis(BaseModel):
    """Strict structured review analysis output."""
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        ...,
        description="Sentiment classification: 'positive', 'negative', or 'neutral'"
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Numerical rating from 1 to 5 based on explicit mention or inferred from sentiment"
    )
    pros: List[str] = Field(
        default_factory=list,
        description="Positive aspects directly supported by the review text"
    )
    cons: List[str] = Field(
        default_factory=list,
        description="Negative aspects directly supported by the review text"
    )
    summary: str = Field(
        ...,
        description="Concise summary highlighting the main points of the customer review"
    )

    @field_validator("sentiment", mode="before")
    @classmethod
    def normalize_sentiment(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip().lower()
            if val in ["positive", "negative", "neutral"]:
                return val
        return v

    @field_validator("rating", mode="before")
    @classmethod
    def normalize_rating(cls, v: Any) -> int:
        if isinstance(v, (int, float, str)):
            try:
                num = int(round(float(v)))
                return max(1, min(5, num))
            except (ValueError, TypeError):
                pass
        return v

    @field_validator("pros", "cons", mode="before")
    @classmethod
    def normalize_string_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [v.strip()] if v.strip() else []
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []


class AnalyzeReviewResponse(BaseModel):
    """Standardized API response structure."""
    success: bool
    data: Optional[ReviewAnalysis] = None
    error: Optional[str] = None
