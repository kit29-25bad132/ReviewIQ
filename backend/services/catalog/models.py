"""Canonical Pydantic models for ReviewIQ products, reviews, and quality artifacts."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CanonicalProduct(BaseModel):
    id: Optional[str] = None
    source_product_id: str
    name: str
    brand: str
    category: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_dataset: str = "product_reviews_dataset.csv"
    source_reference: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Analytical / summary enrichments
    review_count: int = 0
    average_rating: float = 0.0
    price_inr: Optional[float] = None


class CanonicalReview(BaseModel):
    id: Optional[str] = None
    product_id: Optional[str] = None
    source_product_id: str
    source_review_id: str
    rating: int
    review_title: Optional[str] = None
    review_text: str
    review_date: Optional[str] = None
    verified_purchase: bool = True
    source_dataset: str = "product_reviews_dataset.csv"
    source_reference: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class CatalogScanResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    database_connected: bool = False
    total_products: int = 0
    total_reviews: int = 0
    total_embeddings: int = 0
    orphan_reviews_count: int = 0
    categories: List[str] = Field(default_factory=list)
    brands: List[str] = Field(default_factory=list)
    dataset_version: Optional[str] = None
    quality_gate_passed: bool = False
    status_summary: str = ""
