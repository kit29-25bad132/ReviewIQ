from typing import Literal, Optional
from pydantic import BaseModel, Field


class DatasetReview(BaseModel):
    id: str
    asin: Optional[str] = None
    product_name: Optional[str] = None
    review_text: str
    actual_rating: int = Field(ge=1, le=5)
    summary: Optional[str] = None
    review_date: Optional[str] = None
    helpful_yes: Optional[int] = None
    total_vote: Optional[int] = None
    actual_sentiment: Literal["positive", "neutral", "negative"]


class DatasetReviewsResponse(BaseModel):
    items: list[DatasetReview]
    total: int
    limit: int
    offset: int


class OverviewAnalytics(BaseModel):
    total_reviews: int
    average_rating: float
    positive_reviews: int
    neutral_reviews: int
    negative_reviews: int
    rating_distribution: Optional[dict[int, int]] = None


class ProductAnalytics(BaseModel):
    asin: Optional[str] = None
    product_name: Optional[str] = None
    review_count: int
    average_actual_rating: float
    average_ai_rating: Optional[float] = None
    positive_reviews: int
    neutral_reviews: int
    negative_reviews: int
    helpful_votes: int


class EvaluationMetrics(BaseModel):
    evaluated_reviews: int
    rating_accuracy: float
    rating_mae: float
    sentiment_accuracy: float
    confusion_matrix: list[list[int]]
    methodology: str
