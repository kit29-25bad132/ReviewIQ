"""Bounded context assembly for the RAG query endpoint (Phase 7E).

New module — the Phase 5/P3 ``services/rag/context_builder.py`` is a
different contract for a different consumer and is never touched here.

Contract highlights:
* reviews are ordered by similarity (desc), review_id (asc) — deterministic.
* budget: 1 token ≈ 4 characters; a review is added whole when it fits,
  prefix-truncated when a meaningful fragment still fits (>= MIN_FIT_CHARS),
  otherwise dropped and counted in ``reviews_truncated``.
* every rendered block starts with an inline ``[review_id]`` citation marker.
* ``reviews_used`` always carries the FULL, un-truncated ``RetrievedReview``
  (including full ``review_text``) — evidence excerpts for 7F/7G MUST be cut
  from ``reviews_used[i].review_text``, never from the rendered
  ``context_text`` (which may end with a truncation ellipsis).
"""

import math
from dataclasses import dataclass
from typing import Sequence, Tuple

from services.rag.similar_reviews import RetrievedReview

DEFAULT_MAX_TOKENS = 3000
MAX_TOKENS_LIMIT = 20_000
CHARS_PER_TOKEN = 4
MIN_FIT_CHARS = 200
TRUNCATION_SUFFIX = "…"


@dataclass(frozen=True)
class RAGContext:
    """Rendered context block plus build statistics (Phase 7E contract)."""

    reviews_used: Tuple[RetrievedReview, ...]
    context_text: str
    token_estimate: int
    reviews_truncated: int


def _sort_key(review: RetrievedReview):
    return (-float(review.similarity_score), str(review.review_id))


def _header(review: RetrievedReview, text: str) -> str:
    fields = []
    if review.rating is not None:
        fields.append(f"rating={review.rating}")
    fields.append(f"similarity={review.similarity_score:.4f}")
    return f"[{review.review_id}] ({', '.join(fields)}) {text}"


def _truncate_prefix(text: str, max_chars: int) -> str:
    """Verbatim prefix cut at a word boundary, plus a truncation marker."""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    cut = max_chars - len(TRUNCATION_SUFFIX)
    if cut < 1:
        return TRUNCATION_SUFFIX
    head = text[:cut]
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return head + TRUNCATION_SUFFIX


def build_rag_context(
    retrieved_reviews: Sequence[RetrievedReview],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> RAGContext:
    """Select, budget, and render retrieved reviews into a context block.

    Raises ValueError for an invalid ``max_tokens``. Empty input yields an
    empty context — nothing is ever fabricated.
    """
    if (
        not isinstance(max_tokens, int)
        or isinstance(max_tokens, bool)
        or not 1 <= max_tokens <= MAX_TOKENS_LIMIT
    ):
        raise ValueError(
            f"max_tokens must be an integer between 1 and {MAX_TOKENS_LIMIT}."
        )

    ordered = sorted(retrieved_reviews, key=_sort_key)
    budget_chars = max_tokens * CHARS_PER_TOKEN

    block = ""
    used = []
    dropped = 0

    for review in ordered:
        text = review.review_text or ""
        if not text.strip():
            dropped += 1
            continue

        separator = "\n\n" if block else ""
        candidate = f"{separator}{_header(review, text)}"
        if len(block) + len(candidate) <= budget_chars:
            block = f"{block}{candidate}"
            used.append(review)
            continue

        remaining = budget_chars - len(block) - len(separator)
        if remaining < MIN_FIT_CHARS:
            dropped += 1
            continue

        header = _header(review, "")
        text_budget = remaining - len(header)
        if text_budget < 1:
            dropped += 1
            continue

        cut_text = _truncate_prefix(text, text_budget)
        if not cut_text.strip():
            dropped += 1
            continue
        block = f"{block}{separator}{header}{cut_text}"
        # reviews_used keeps the FULL untruncated review; only the rendered
        # block is cut. 7F/7G excerpts come from review_text, not this block.
        used.append(review)

    token_estimate = math.ceil(len(block) / CHARS_PER_TOKEN) if block else 0
    return RAGContext(
        reviews_used=tuple(used),
        context_text=block,
        token_estimate=token_estimate,
        reviews_truncated=dropped,
    )
