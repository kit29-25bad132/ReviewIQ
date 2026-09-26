"""Deterministic review deduplication.

Fingerprint = sha256(product_id + canonicalized text). Product ID participates
so identical text for two different products is *not* collapsed into one stored
review (the data model keys reviews by product context). Canonicalization is
NFKC + casefold + whitespace collapse, so exact duplicates and
whitespace/case-only variants share a fingerprint without any LLM involvement.

Deduplication never deletes source data; it only prevents redundant vector
records and redundant embedding calls.
"""

import hashlib
import re
import unicodedata
from typing import List, Optional, Sequence

from services.retrieval.contracts import (
    DeduplicationReport,
    PreparedReview,
    ValidatedReview,
)
from services.retrieval.preprocessing import preprocess_review_text

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)
_FIELD_SEPARATOR = "\x1f"


def canonicalize_for_fingerprint(text: str) -> str:
    """Case/whitespace-insensitive canonical form used only for fingerprinting."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized.casefold().strip()


def review_fingerprint(product_id: Optional[str], text: str) -> str:
    """Stable sha256 fingerprint over product id + canonical text."""
    canonical = canonicalize_for_fingerprint(text)
    product = (product_id or "").strip()
    payload = f"{product}{_FIELD_SEPARATOR}{canonical}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prepare_review(review: ValidatedReview) -> PreparedReview:
    """Preprocess one validated review and attach its deterministic fingerprint."""
    normalized_text = preprocess_review_text(review.review_text)
    fingerprint = review_fingerprint(review.product_id, normalized_text)
    return PreparedReview(
        review=review, normalized_text=normalized_text, fingerprint=fingerprint
    )


def dedupe_prepared(reviews: Sequence[PreparedReview]) -> DeduplicationReport:
    """Split prepared reviews into unique (first occurrence wins) and duplicates."""
    seen = set()
    accepted: List[PreparedReview] = []
    duplicates: List[PreparedReview] = []
    for review in reviews:
        if review.fingerprint in seen:
            duplicates.append(review)
        else:
            seen.add(review.fingerprint)
            accepted.append(review)
    return DeduplicationReport(accepted=tuple(accepted), duplicates=tuple(duplicates))
