from typing import List, Optional
from pydantic import BaseModel, Field


class ProductSummary(BaseModel):
    product_id: str
    product_title: str
    category: Optional[str] = None
    review_count: int = 0
    average_rating: float = 0.0


class ProductSearchResponse(BaseModel):
    found: bool
    products: List[ProductSummary] = Field(default_factory=list)
    message: Optional[str] = None


class ProductStatistics(BaseModel):
    review_count: int
    average_rating: float
    rating_distribution: dict[str, int]
    sentiment_distribution: dict[str, int]


class ReviewItem(BaseModel):
    id: int
    product_id: str
    product_title: str
    category: Optional[str] = None
    review_text: str
    rating: int
    sentiment: str


class ProductAnalysisResponse(BaseModel):
    product: ProductSummary
    statistics: ProductStatistics
    recent_reviews: List[ReviewItem] = Field(default_factory=list)


class ReviewsPaginationResponse(BaseModel):
    items: List[ReviewItem]
    total: int
    page: int
    limit: int
    total_pages: int


class AISummaryResponse(BaseModel):
    summary: str
    common_pros: List[str] = Field(default_factory=list)
    common_cons: List[str] = Field(default_factory=list)
    key_themes: List[str] = Field(default_factory=list)
    source_label: str = "Summary generated from dataset reviews"


class ProConTheme(BaseModel):
    theme: str
    review_count: int
    percentage: float
    example_reviews: List[str] = Field(default_factory=list)
    evidence_review_ids: List[int] = Field(default_factory=list)


class ProsConsAnalysisResponse(BaseModel):
    product_id: str
    product_title: str
    total_analyzed_reviews: int
    pros: List[ProConTheme] = Field(default_factory=list)
    cons: List[ProConTheme] = Field(default_factory=list)
    summary: str
    top_pros: List[str] = Field(default_factory=list)
    top_cons: List[str] = Field(default_factory=list)
    review_volume: int
    average_rating: float
    sentiment_percentages: dict[str, float] = Field(default_factory=dict)
    authenticity_signals: List[str] = Field(default_factory=list)
    source_label: str = "Derived strictly from actual dataset reviews"


class UserRequirementRequest(BaseModel):
    persona: Optional[str] = None
    custom_requirements: Optional[str] = None
    priorities: List[str] = Field(default_factory=list)
    budget: Optional[str] = None


class ProductComparisonItem(BaseModel):
    product_id: str
    product_title: str
    category: str
    average_rating: float
    review_count: int
    positive_percentage: float
    negative_percentage: float
    neutral_percentage: float
    common_pros: List[str] = Field(default_factory=list)
    common_cons: List[str] = Field(default_factory=list)
    is_selected: bool = False


class PriorityMatchEvidence(BaseModel):
    priority: str
    evidence_level: str
    details: str
    supporting_reviews: List[str] = Field(default_factory=list)


class PersonalizedRecommendationResponse(BaseModel):
    selected_product: ProductSummary
    recommended_product: ProductSummary
    user_priorities: List[str] = Field(default_factory=list)
    priority_matches: List[PriorityMatchEvidence] = Field(default_factory=list)
    suitability_verdict: str
    suitable_for: List[str] = Field(default_factory=list)
    consider_before_buying: List[str] = Field(default_factory=list)
    comparison_products: List[ProductComparisonItem] = Field(default_factory=list)
    recommendation_headline: str
    recommendation_reasons: List[str] = Field(default_factory=list)
    strengths_for_you: List[str] = Field(default_factory=list)
    things_to_consider: List[str] = Field(default_factory=list)
    source_label: str = "Personalized recommendation derived strictly from dataset review evidence"
