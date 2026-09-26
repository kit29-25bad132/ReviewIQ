"""Deterministic review preprocessing for semantic embedding.

Normalization only — it never paraphrases, removes stop words, stems, or
changes wording. Punctuation and case are preserved because they carry
sentiment ("AMAZING!!!" vs "amazing"). The original review text is always kept
separately for evidence grounding.
"""

import re
import unicodedata
from typing import Sequence

# Control characters, excluding tab/newline/carriage-return which are handled
# as whitespace. Replaced with a space (not deleted) to preserve word breaks.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Zero-width / bidi formatting characters that carry no semantic content.
_ZERO_WIDTH_RE = re.compile("[\u200b-\u200f\u202a-\u202e\ufeff]")
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def preprocess_review_text(text: str) -> str:
    """Normalize whitespace/control characters deterministically.

    Example:
        "  Battery is AMAZING!!! \\n\\n  but heats up. " -> "Battery is AMAZING!!! but heats up."
    """
    if not isinstance(text, str):
        raise TypeError("preprocess_review_text expects a string")

    normalized = unicodedata.normalize("NFKC", text)
    normalized = _ZERO_WIDTH_RE.sub("", normalized)
    normalized = _CONTROL_RE.sub(" ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


def preprocess_reviews(texts: Sequence[str]) -> list:
    """Preprocess many texts, preserving order."""
    return [preprocess_review_text(text) for text in texts]
