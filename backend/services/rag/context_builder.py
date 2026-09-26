"""Bounded, deterministic context built from retrieved reviews (V2-P3).

The context feeds the RAG prompt only. It never replaces the original review
and never passes through evidence grounding (grounding stays original-review
only — see ``services/grounding_service.py``).

Input order from the retrieval stage (similarity desc, review_id tie-break) is
preserved; malformed entries are skipped and counted, never fabricated.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from services.rag.config import RAGConfig
from services.retrieval.vector_repository import ReviewSearchResult

TRUNCATION_MARKER = " ...[truncated]"
# Smallest text fragment worth adding when the total char budget forces a fit.
_MIN_FIT_CHARS = 8


@dataclass(frozen=True)
class ContextReview:
    """One retrieved review selected for the context block."""

    review_id: str
    text: str
    similarity: float
    rating: Optional[int]
    product_id: Optional[str]
    source: Optional[str]
    truncated: bool = False


@dataclass(frozen=True)
class RagContext:
    """Rendered context block plus build statistics."""

    reviews: Tuple[ContextReview, ...]
    block: str
    truncated: bool
    skipped: int

    @property
    def is_empty(self) -> bool:
        return not self.reviews

    @property
    def char_count(self) -> int:
        return len(self.block)


def render_context_block(context: Optional[RagContext]) -> str:
    """Return the rendered context block ('' for None/empty)."""
    if context is None:
        return ""
    return context.block


def _is_finite(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _truncate_text(text: str, max_chars: int) -> Tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    budget = max_chars - len(TRUNCATION_MARKER)
    if budget < 1:
        # No room for the marker: hard cut so the result still fits max_chars.
        return text[:max_chars], True
    head = text[:budget]
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return head + TRUNCATION_MARKER, True


def _metadata_line(index: int, review: ContextReview) -> str:
    fields = [f"similarity={review.similarity:.4f}"]
    if isinstance(review.rating, int) and not isinstance(review.rating, bool):
        fields.append(f"rating={review.rating}")
    if isinstance(review.product_id, str) and review.product_id:
        fields.append(f"product_id={review.product_id}")
    if isinstance(review.source, str) and review.source:
        fields.append(f"source={review.source}")
    fields.append(f"review_id={review.review_id}")
    return f"[{index}] " + " | ".join(fields)


def build_rag_context(
    results: Sequence[ReviewSearchResult], config: RAGConfig
) -> RagContext:
    """Select, cap, and render retrieved reviews into a context block.

    Guarantees: deterministic output for the same input, ``char_count`` never
    exceeds ``config.max_context_chars`` and never includes more than
    ``config.max_context_reviews`` reviews.
    """
    reviews: List[ContextReview] = []
    skipped = 0
    truncated_any = False

    for item in results:
        if len(reviews) >= config.max_context_reviews:
            break
        review_id = getattr(item, "review_id", None)
        text = getattr(item, "review_text", None)
        similarity = getattr(item, "similarity", None)
        if not isinstance(review_id, str) or not review_id.strip():
            skipped += 1
            continue
        if not isinstance(text, str) or not text.strip():
            skipped += 1
            continue
        if not _is_finite(similarity):
            skipped += 1
            continue

        rating = getattr(item, "rating", None)
        product_id = getattr(item, "product_id", None)
        source = getattr(item, "source", None)
        reviews.append(
            ContextReview(
                review_id=review_id,
                text=text,
                similarity=float(similarity),
                rating=rating if isinstance(rating, int) and not isinstance(rating, bool) else None,
                product_id=product_id if isinstance(product_id, str) else None,
                source=source if isinstance(source, str) else None,
            )
        )

    block = ""
    final: List[ContextReview] = []
    for index, review in enumerate(reviews, start=1):
        text, was_truncated = _truncate_text(review.text, config.max_review_chars)
        line = _metadata_line(index, review)
        separator = "\n\n" if block else ""
        candidate = f"{separator}{line}\n{text}"
        if len(block) + len(candidate) > config.max_context_chars:
            remaining = (
                config.max_context_chars
                - len(block)
                - len(separator)
                - len(line)
                - 1
            )
            if remaining < len(TRUNCATION_MARKER) + _MIN_FIT_CHARS:
                break
            fitted, _ = _truncate_text(text, remaining)
            if len(fitted) > remaining or len(fitted) < _MIN_FIT_CHARS:
                break
            block = f"{block}{separator}{line}\n{fitted}"
            final.append(
                ContextReview(
                    review_id=review.review_id,
                    text=fitted,
                    similarity=review.similarity,
                    rating=review.rating,
                    product_id=review.product_id,
                    source=review.source,
                    truncated=True,
                )
            )
            truncated_any = True
            break
        block = f"{block}{candidate}"
        final.append(
            ContextReview(
                review_id=review.review_id,
                text=text,
                similarity=review.similarity,
                rating=review.rating,
                product_id=review.product_id,
                source=review.source,
                truncated=was_truncated,
            )
        )
        truncated_any = truncated_any or was_truncated

    return RagContext(
        reviews=tuple(final),
        block=block,
        truncated=truncated_any,
        skipped=skipped,
    )
