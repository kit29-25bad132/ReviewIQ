"""V2 retrieval API contracts (semantic search).

Kept separate from V1 models so no existing response contract changes. These
models are additive and only used by the ``/api/v2/retrieval`` endpoints.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SemanticSearchRequest(BaseModel):
    """Semantic similarity search over stored review embeddings."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Natural-language query to find similar reviews for",
    )
    top_k: int = Field(
        default=10, ge=1, le=100, description="Maximum number of similar reviews"
    )
    similarity_threshold: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Optional minimum cosine similarity (omit to accept all matches)",
    )
    product_id: Optional[str] = Field(
        default=None, description="Restrict results to one product id"
    )
    min_rating: Optional[int] = Field(default=None, ge=1, le=5)
    max_rating: Optional[int] = Field(default=None, ge=1, le=5)
    source: Optional[str] = Field(default=None, description="Restrict to a data source")
    review_date_from: Optional[datetime] = None
    review_date_to: Optional[datetime] = None

    @field_validator("query")
    @classmethod
    def strip_and_validate_query(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Query cannot be empty or whitespace only.")
        return trimmed

    @model_validator(mode="after")
    def validate_rating_range(self) -> "SemanticSearchRequest":
        if (
            self.min_rating is not None
            and self.max_rating is not None
            and self.min_rating > self.max_rating
        ):
            raise ValueError("min_rating cannot be greater than max_rating")
        return self


class SemanticSearchResultItem(BaseModel):
    """One similar review returned from semantic search."""

    review_id: str
    product_id: Optional[str] = None
    review_text: str
    similarity: float
    distance: float
    rating: Optional[int] = None
    source: Optional[str] = None
    embedding_model: str


class SemanticSearchResponse(BaseModel):
    """Additive V2 semantic search response (no V1 contract is altered)."""

    success: bool = True
    query: str
    top_k: int
    similarity_threshold: Optional[float] = None
    embedding_model: str
    embedding_dimension: int
    result_count: int
    results: List[SemanticSearchResultItem] = Field(default_factory=list)
    error: Optional[str] = None


class RetrievalStatusResponse(BaseModel):
    """Non-secret retrieval configuration status."""

    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embeddings_configured: bool
    database_configured: bool
    similarity_metric: str
