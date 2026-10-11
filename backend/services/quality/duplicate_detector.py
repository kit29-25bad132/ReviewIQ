"""Multi-Level Duplicate and Template Repetition Detector for ReviewIQ.

Implements:
- LEVEL 1: Exact duplicates
- LEVEL 2: Normalized duplicates
- LEVEL 3: Near duplicates (Jaccard token similarity on n-grams)
- LEVEL 4: Template & skeleton repetition detection
"""

import re
import string
from collections import Counter, defaultdict
from typing import Any, Dict, List, Set, Tuple


def normalize_text(text: str) -> str:
    """Deterministic normalization: lowercased, punctuation removed, whitespace collapsed."""
    text_lower = text.lower()
    text_clean = text_lower.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", text_clean).strip()


def get_ngrams(text: str, n: int = 3) -> Set[str]:
    """Extract character n-grams for fuzzy near-duplicate matching."""
    norm = normalize_text(text)
    if len(norm) < n:
        return {norm}
    return {norm[i:i+n] for i in range(len(norm) - n + 1)}


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Computes Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union if union > 0 else 0.0


def extract_template_skeleton(text: str) -> str:
    """Extracts structural skeleton by masking numbers, specific nouns/brands with placeholders."""
    norm = normalize_text(text)
    # Mask numbers
    skeleton = re.sub(r"\b\d+\b", "<NUM>", norm)
    # Mask common tech specs
    skeleton = re.sub(r"\b(mah|gb|tb|hz|fps|inch|watts|w|v|mm|kg|g)\b", "<SPEC>", skeleton)
    return skeleton


def _near_duplicate_pairs(ngram_cache, threshold: float) -> List[Dict[str, Any]]:
    """Order-independent exhaustive near-duplicate detection.

    Compares EVERY pair (no sampling window). Pairs whose char-3-gram set
    size ratio is below the threshold are pruned: Jaccard can never reach
    the threshold then, so pruning loses zero recall. Normalized-text
    duplicates are Level 2's jurisdiction and are excluded here to avoid
    double counting. Output sorted by (review_a, review_b) with IDs ordered
    within each pair — identical input in any row order yields identical
    output.
    """
    prepared = [
        (rid, text, norms) for rid, text, norms in ngram_cache if norms
    ]
    pairs = []
    for i in range(len(prepared)):
        rid_a, text_a, set_a = prepared[i]
        norm_a = normalize_text(text_a)
        for j in range(i + 1, len(prepared)):
            rid_b, text_b, set_b = prepared[j]
            if norm_a == normalize_text(text_b):
                continue  # counted at Level 2, not here
            small, large = (len(set_a), len(set_b)) if len(set_a) <= len(set_b) else (len(set_b), len(set_a))
            if large == 0 or small / large < threshold:
                continue  # provably cannot reach threshold
            sim = jaccard_similarity(set_a, set_b)
            if sim >= threshold:
                first, second = sorted((str(rid_a), str(rid_b)))
                pairs.append({
                    "review_a": first,
                    "review_b": second,
                    "similarity": round(sim, 3),
                    "sample": text_a[:80],
                })
    pairs.sort(key=lambda p: (p["review_a"], p["review_b"]))
    return pairs


class DuplicateDetector:
    """Analyzes exact, normalized, near, and template duplicates across review collections."""

    def analyze(self, reviews: List[Dict[str, Any]], near_dup_threshold: float = 0.85) -> Dict[str, Any]:
        total_reviews = len(reviews)
        if total_reviews == 0:
            return {
                "total_reviews": 0,
                "exact_duplicates": {"count": 0, "percentage": 0.0, "examples": []},
                "normalized_duplicates": {"count": 0, "percentage": 0.0, "examples": []},
                "near_duplicates": {"count": 0, "percentage": 0.0, "examples": []},
                "template_repetitions": {"count": 0, "percentage": 0.0, "examples": []},
            }

        # Level 1: Exact Duplicates
        exact_counter = Counter(r.get("review_text", "") for r in reviews)
        exact_dup_count = sum(c - 1 for text, c in exact_counter.items() if c > 1 and text.strip())
        exact_examples = [text[:100] for text, c in exact_counter.items() if c > 1 and text.strip()][:5]

        # Level 2: Normalized Duplicates
        norm_map = defaultdict(list)
        for r in reviews:
            norm = normalize_text(r.get("review_text", ""))
            if norm:
                norm_map[norm].append(r.get("review_id"))
        
        norm_dup_count = sum(len(ids) - 1 for ids in norm_map.values() if len(ids) > 1)
        norm_examples = [k[:100] for k, ids in norm_map.items() if len(ids) > 1][:5]

        # Level 3: Near Duplicates (exhaustive, order-independent — see _near_duplicate_pairs)
        ngram_cache = [(r.get("review_id"), r.get("review_text", ""), get_ngrams(r.get("review_text", ""))) for r in reviews]
        near_dup_pairs = _near_duplicate_pairs(ngram_cache, near_dup_threshold)

        near_dup_count = len(near_dup_pairs)

        # Level 4: Template / Skeleton Repetitions
        skeleton_map = defaultdict(list)
        for r in reviews:
            skel = extract_template_skeleton(r.get("review_text", ""))
            if len(skel) > 20:  # Ignore trivial 1-word skeletons
                skeleton_map[skel].append(r.get("review_id"))

        template_rep_count = sum(len(ids) - 1 for ids in skeleton_map.values() if len(ids) > 2)
        template_examples = [
            {"skeleton": k[:100], "repetition_count": len(ids)}
            for k, ids in skeleton_map.items() if len(ids) > 2
        ][:5]

        return {
            "total_reviews": total_reviews,
            "exact_duplicates": {
                "count": exact_dup_count,
                "percentage": round((exact_dup_count / total_reviews) * 100, 2),
                "examples": exact_examples,
            },
            "normalized_duplicates": {
                "count": norm_dup_count,
                "percentage": round((norm_dup_count / total_reviews) * 100, 2),
                "examples": norm_examples,
            },
            "near_duplicates": {
                "count": near_dup_count,
                "percentage": round((near_dup_count / total_reviews) * 100, 2),
                "examples": near_dup_pairs[:5],
            },
            "template_repetitions": {
                "count": template_rep_count,
                "percentage": round((template_rep_count / total_reviews) * 100, 2),
                "examples": template_examples,
            },
        }


duplicate_detector = DuplicateDetector()
