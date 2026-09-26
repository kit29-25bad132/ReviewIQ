"""Retrieval-domain contracts: validated reviews, prepared reviews, reports.

``ValidatedReview`` is Pydantic (the internal review representation). The
remaining types are lightweight frozen dataclasses for deterministic pipeline
outputs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

# Maximum accepted review length. Over-length reviews are rejected explicitly
# rather than silently truncated (never manufacture or corrupt review content).
MAX_REVIEW_TEXT_LENGTH = 20_000


class ValidationOutcome(str, Enum):
    """Explicit outcome of validating one raw review record."""

    VALID = "valid"
    INVALID_MISSING_TEXT = "invalid_missing_text"
    INVALID_EMPTY_TEXT = "invalid_empty_text"
    INVALID_TEXT_TOO_LONG = "invalid_text_too_long"
    INVALID_METADATA = "invalid_metadata"
    INVALID_MALFORMED = "invalid_malformed"


class ValidatedReview(BaseModel):
    """Canonical internal representation of a review entering retrieval."""

    model_config = ConfigDict(frozen=True)

    review_id: Optional[str] = Field(
        default=None, description="Source review identifier when available"
    )
    product_id: Optional[str] = None
    review_text: str = Field(..., description="Original review text (stripped)")
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    title: Optional[str] = None
    source: Optional[str] = None
    review_date: Optional[datetime] = None


@dataclass(frozen=True)
class RejectedReview:
    """A record that did not validate, with an explicit reason."""

    outcome: ValidationOutcome
    reason: str
    review_id: Optional[str] = None
    product_id: Optional[str] = None


@dataclass(frozen=True)
class ValidationReport:
    accepted: Tuple[ValidatedReview, ...] = ()
    rejected: Tuple[RejectedReview, ...] = ()


@dataclass(frozen=True)
class PreparedReview:
    """A validated review after preprocessing and fingerprinting."""

    review: ValidatedReview
    normalized_text: str
    fingerprint: str

    @property
    def review_id(self) -> str:
        """Stable id: the source id when present, else the fingerprint."""
        return self.review.review_id or self.fingerprint

    @property
    def product_id(self) -> Optional[str]:
        return self.review.product_id


@dataclass(frozen=True)
class DeduplicationReport:
    accepted: Tuple[PreparedReview, ...] = ()
    duplicates: Tuple[PreparedReview, ...] = ()


@dataclass(frozen=True)
class IndexingReport:
    """Outcome of indexing a batch of raw reviews."""

    received: int
    accepted: int
    duplicates: int
    invalid: int
    already_indexed: int
    indexed: int
    failed: int
    rejected: Tuple[RejectedReview, ...] = ()
    failed_review_ids: Tuple[str, ...] = ()
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    metadata: dict = field(default_factory=dict)
