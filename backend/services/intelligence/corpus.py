"""Shared read layer for the Phase 5 intelligence stages.

Every 5B/5C/5D stage starts from the same thing: the real canonical product
record plus the real reviews retrieved from the database. This module is that
single entry point, so no stage can quietly substitute its own source.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from services.catalog.catalog_service import canonical_catalog

logger = logging.getLogger(__name__)

#: Upper bound on reviews pulled into a single product's corpus. Every product
#: in the canonical dataset has far fewer than this (max 95 at time of
#: writing), so this is a guard against pathological data, not a sampling
#: choice — the whole corpus is used.
MAX_CORPUS_REVIEWS = 1000


def load_product_corpus(
    product_id_or_source_id: str,
    limit: int = MAX_CORPUS_REVIEWS,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return ``(product, reviews)`` for a product, or ``(None, [])``.

    Review rows are the raw canonical dicts (``source_review_id``,
    ``review_text``, ``rating``, ``sentiment``, ...). No transformation happens
    here, so grounding stages can compare model output against verbatim text.
    """
    clean_id = str(product_id_or_source_id).strip()
    product = canonical_catalog.get_product_by_id(clean_id)
    if product is None:
        return None, []

    reviews, _ = canonical_catalog.get_reviews(
        clean_id, page=1, page_size=limit, sort_by="date_desc", product=product
    )
    return product, reviews


def format_review_samples(reviews: List[Dict[str, Any]]) -> List[str]:
    """Format canonical reviews for a prompt: ``[Review <id> | <sent| <rating>★] text``.

    The format matches ``routes.products.format_canonical_samples`` so any
    prompt already validated against the legacy path sees an identical shape.
    The review text is passed through unmodified, which is what makes verbatim
    quote grounding possible downstream.
    """
    return [
        f"[Review {r.get('source_review_id')} | {r.get('sentiment', 'neutral')} | "
        f"{r.get('rating')}★] {r.get('review_text', '')}"
        for r in reviews
    ]
