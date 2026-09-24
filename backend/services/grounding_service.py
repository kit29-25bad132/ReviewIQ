"""Phase 2: deterministic evidence grounding against the original review text.

Core invariant: the API must never return an evidence string that is not
supported by the original review text.

V1 behavior (documented):
- Every evidence-bearing item (pros[].evidence, cons[].evidence,
  aspects[].evidence) is checked against the original review using
  deterministic normalized containment (no fuzzy matching, no embeddings).
- Unsupported items are removed entirely from the analysis. Fabricated
  evidence never reaches the API response.
- Empty or whitespace-only evidence is never considered grounded.
- Claims (point / aspect) are NOT substring-validated; a concise point may
  summarize its evidence. Grounding applies only to the evidence string.
- Standard library only: no network calls, no external models.

Normalization handles case (casefold), whitespace (collapse), punctuation
(replaced with spaces so word boundaries are preserved), and common
quote/apostrophe variants.
"""

import re
import unicodedata

from models.review import AspectSentiment, PointEvidence, ReviewAnalysis

# Common typographic quotes / apostrophes mapped to ASCII equivalents so that
# curly and straight variants normalize identically.
_CHAR_MAP = {
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote / apostrophe
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u201e": '"',
    "\u00a0": " ",  # non-breaking space
}

# Replace anything that is not a word character or whitespace with a space.
# Replacing (rather than deleting) preserves word boundaries: "day.and" -> "day and".
_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def normalize_text(text: str) -> str:
    """Deterministic normalization for evidence matching.

    Applies NFKC unicode normalization, quote/apostrophe mapping,
    casefold(), punctuation-to-space, and whitespace collapsing.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    for src, dst in _CHAR_MAP.items():
        normalized = normalized.replace(src, dst)
    normalized = normalized.casefold()
    normalized = _PUNCTUATION_RE.sub(" ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


def is_evidence_supported(review_text: str, evidence: str) -> bool:
    """Return True only if the entire evidence claim appears in the review
    after deterministic normalization (normalized containment).

    Empty / whitespace-only evidence is never supported. A shared keyword
    alone is not sufficient: the whole normalized evidence string must be a
    substring of the normalized review.
    """
    normalized_review = normalize_text(review_text)
    normalized_evidence = normalize_text(evidence)
    if not normalized_evidence:
        return False
    return normalized_evidence in normalized_review


def ground_analysis(review_text: str, analysis: ReviewAnalysis) -> ReviewAnalysis:
    """Return a grounded copy of the analysis.

    Removes every pro, con, or aspect whose evidence string is not supported
    by the original review text. Items with supported evidence are kept
    unchanged. Never invents, rewrites, or replaces evidence.
    """
    grounded_pros = [
        p for p in analysis.pros
        if is_evidence_supported(review_text, p.evidence)
    ]
    grounded_cons = [
        c for c in analysis.cons
        if is_evidence_supported(review_text, c.evidence)
    ]
    grounded_aspects = [
        a for a in analysis.aspects
        if is_evidence_supported(review_text, a.evidence)
    ]
    return analysis.model_copy(update={
        "pros": grounded_pros,
        "cons": grounded_cons,
        "aspects": grounded_aspects,
    })
