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

V2-P4 additions (documented decisions):
- Duplicate supported evidence within a single collection (pros / cons /
  aspects) is removed: identity is the exact same normalization used for
  grounding, first occurrence wins, the survivor keeps its original
  evidence text, and otherwise order is preserved. Dedupe never crosses
  collections (the contract keeps pros, cons, and aspects independent).
- Numeric confidence is intentionally NOT exposed: any number would be fake
  statistics.
- Relevance is textual support only: no fuzzy matching, no embeddings,
  no second model (claim<->evidence semantic similarity is out of scope
  by design).

V2-P8 additions (documented decisions):
- ``AspectSentiment.support`` is a deterministic, application-computed
  evidence-support level (``strong`` / ``moderate`` / ``weak``). It is NOT a
  model output and NOT a probability: the model is never trusted to supply it,
  and ``ground_analysis`` overwrites it after grounding. A removed aspect can
  never carry a support status because it does not survive the filter.
- Classification is a pure function of application-known facts: whether the
  evidence is grounded, whether it is a verbatim substring of the original
  review, and whether it mentions the aspect (shared normalized token). No
  fuzzy matching, no embeddings, no invented score, no second model.

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


def _dedupe_supported_evidence(items: list) -> list:
    """Keep the first item of each normalized-evidence identity (V2-P4).

    Must be called only with items whose evidence already passed
    ``is_evidence_supported`` (so every key is non-empty). Comparison uses
    the exact same ``normalize_text`` as grounding — no second algorithm —
    so case/punctuation/whitespace variants collapse into one identity,
    while distinct evidence that merely shares keywords stays distinct.
    The surviving item keeps its original evidence text unchanged and
    input order is preserved.
    """
    seen = set()
    kept = []
    for item in items:
        key = normalize_text(item.evidence)
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


# V2-P8: deterministic evidence-support levels (see module docstring).
SUPPORT_STRONG = "strong"
SUPPORT_MODERATE = "moderate"
SUPPORT_WEAK = "weak"

# A token must be at least this long to count as "the evidence mentions the
# aspect". This is a fixed, documented rule (not a tuned score) that avoids
# matching on trivial one-character tokens.
_MIN_COVERAGE_TOKEN_LEN = 2


def _coverage_tokens(normalized_text: str) -> set:
    """Content tokens used for the deterministic aspect-mention check."""
    return {
        token
        for token in normalized_text.split()
        if len(token) >= _MIN_COVERAGE_TOKEN_LEN
    }


def classify_aspect_support(review_text: str, aspect: str, evidence: str) -> str:
    """Deterministic evidence-support level for one aspect (V2-P8).

    Rules (application-known facts only; no model self-report, no probability):
      * unsupported evidence -> ``weak`` (defensive; such aspects are removed
        by grounding before classification, so this can never surface in an
        analysis result);
      * grounded + verbatim substring of the original review + mentions the
        aspect -> ``strong``;
      * grounded + mentions the aspect (match only after normalization) ->
        ``moderate``;
      * grounded but does not mention the aspect -> ``weak``.

    "Mentions the aspect" means the normalized aspect and normalized evidence
    share at least one token of length >= 2. Evidence support is textual only:
    no fuzzy matching, no embeddings, no numeric score.
    """
    if not is_evidence_supported(review_text, evidence):
        return SUPPORT_WEAK
    stripped = (evidence or "").strip()
    verbatim = bool(stripped) and stripped in review_text
    mentions_aspect = bool(
        _coverage_tokens(normalize_text(aspect))
        & _coverage_tokens(normalize_text(evidence))
    )
    if mentions_aspect and verbatim:
        return SUPPORT_STRONG
    if mentions_aspect:
        return SUPPORT_MODERATE
    return SUPPORT_WEAK


def ground_analysis(review_text: str, analysis: ReviewAnalysis) -> ReviewAnalysis:
    """Return a grounded copy of the analysis.

    Removes every pro, con, or aspect whose evidence string is not supported
    by the original review text, then removes duplicate supported evidence
    within each collection (first occurrence wins). Items that survive are
    kept unchanged, except that each surviving aspect receives its
    deterministic, application-computed ``support`` level (V2-P8). Never
    invents, rewrites, or replaces evidence. The original review remains the
    only authoritative source; retrieved RAG context is never consulted here.
    """
    grounded_pros = _dedupe_supported_evidence([
        p for p in analysis.pros
        if is_evidence_supported(review_text, p.evidence)
    ])
    grounded_cons = _dedupe_supported_evidence([
        c for c in analysis.cons
        if is_evidence_supported(review_text, c.evidence)
    ])
    supported_aspects = _dedupe_supported_evidence([
        a for a in analysis.aspects
        if is_evidence_supported(review_text, a.evidence)
    ])
    grounded_aspects = [
        a.model_copy(
            update={
                "support": classify_aspect_support(
                    review_text, a.aspect, a.evidence
                )
            }
        )
        for a in supported_aspects
    ]
    return analysis.model_copy(update={
        "pros": grounded_pros,
        "cons": grounded_cons,
        "aspects": grounded_aspects,
    })
