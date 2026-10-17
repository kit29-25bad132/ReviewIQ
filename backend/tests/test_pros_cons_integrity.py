"""Gate 2 (Phase 4): pros/cons evidence integrity.

Uses mocked canonical-catalog statistics and review rows (no writes to any
real database, no live providers). Proves that:
- fabricated fallback quotations can never be returned;
- evidence quotes trace to actual source reviews;
- the analyzed sample size is distinguished from the available review pool;
- projected counts follow the documented formula and denominator;
- unsupported authenticity/correlation claims are absent.
"""

from unittest.mock import patch

from services.catalog.catalog_service import canonical_catalog
from services.pros_cons_service import pros_cons_service

FABRICATED_QUOTES = (
    "Satisfied with the overall purchase.",
    "Did not meet customer expectations.",
)
UNSUPPORTED_CLAIMS = (
    "Zero synthetic",
    "correlates",
    "verified dataset reviews",
    "Rating spread spans all 5 tiers",
)

# Guaranteed non-matching review text: contains none of the theme keywords.
NEUTRAL_TEXT = "Zzqjj. Uuvvxw rt qmnp. Blix wooben."
# Guaranteed matching text for "Product Performance & Reliability"
# (keywords "works" / "perfect").
MATCHING_TEXT = "It works perfectly for my daily routine."


def _stats(total, average_rating, positive, neutral, negative):
    """Canonical product-statistics dict shaped like the real catalog output."""
    return {
        "product": {
            "id": "00000000-0000-0000-0000-000000000001",
            "source_product_id": "P1",
            "product_title": "Selected Product",
            "category": "Category",
        },
        "total_reviews": total,
        "average_rating": average_rating,
        "rating_distribution": {
            "star_1": 0,
            "star_2": 0,
            "star_3": 0,
            "star_4": 0,
            "star_5": 0,
        },
        "sentiment_distribution": {
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
        },
    }


def _rows(*specs):
    """Canonical review rows: (review_text, rating, sentiment) with stable
    string IDs, as produced by CanonicalCatalogService."""
    return [
        {
            "source_review_id": f"R{i:05d}",
            "source_product_id": "P1",
            "review_text": text,
            "rating": rating,
            "sentiment": sentiment,
        }
        for i, (text, rating, sentiment) in enumerate(specs, start=1)
    ]


def _analyze(stats, rows):
    with patch.object(canonical_catalog, "is_configured", return_value=True), patch.object(
        canonical_catalog, "get_product_statistics", return_value=stats
    ), patch.object(
        canonical_catalog, "get_reviews", return_value=(rows, len(rows))
    ):
        return pros_cons_service.analyze_product_pros_cons("P1")


def test_no_fabricated_fallback_quotes_when_no_theme_matches():
    # 6 real reviews, none matching any theme keyword; product has real
    # positive/negative counts so the fallback aggregate themes appear.
    stats = _stats(total=6, average_rating=4.0, positive=4, neutral=1, negative=1)
    rows = _rows(
        (NEUTRAL_TEXT, 5, "positive"),
        (NEUTRAL_TEXT, 4, "positive"),
        (NEUTRAL_TEXT, 4, "positive"),
        (NEUTRAL_TEXT, 5, "positive"),
        (NEUTRAL_TEXT, 3, "neutral"),
        (NEUTRAL_TEXT, 1, "negative"),
    )
    result = _analyze(stats, rows)
    payload = result.model_dump_json()

    for quote in FABRICATED_QUOTES:
        assert quote not in payload
    for claim in UNSUPPORTED_CLAIMS:
        assert claim not in payload

    # Fallback aggregate themes appear under the current (Phase 5-7) labels and
    # carry only verbatim real reviews as evidence — never fabricated quotes
    # and never IDs outside the actual source rows. (Phase 4 pinned the same
    # anti-fabrication contract against its era's theme labels and empty-list
    # representation; the labels were renamed and real evidence was added by
    # the completed Phase 5-7 architecture, which this gate must not revert.)
    assert result.pros[0].theme == "Positive Customer Experience"
    assert result.cons[0].theme == "Customer Reported Issues"
    real_texts = {NEUTRAL_TEXT}
    real_ids = {r["source_review_id"] for r in rows}
    for theme in (result.pros[0], result.cons[0]):
        for quote in theme.example_reviews:
            assert quote in real_texts
        for eid in theme.evidence_review_ids:
            assert eid in real_ids


def test_evidence_quotes_trace_to_actual_source_reviews():
    stats = _stats(total=1, average_rating=5.0, positive=1, neutral=0, negative=0)
    rows = _rows((MATCHING_TEXT, 5, "positive"))
    result = _analyze(stats, rows)

    assert result.pros
    theme = next(p for p in result.pros if p.theme == "Product Performance & Reliability")
    # The evidence quote is verbatim a real review row, not a template.
    assert theme.example_reviews == [MATCHING_TEXT]
    # Canonical evidence uses stable string IDs (see models/ecommerce.py);
    # the recorded ID must be exactly the source row's ID.
    assert theme.evidence_review_ids == [rows[0]["source_review_id"]]


def test_sample_size_is_distinguished_from_available_pool_and_projection_is_documented():
    # Only 6 reviews exist to analyze, but the product's full pool is 120.
    stats = _stats(total=120, average_rating=4.0, positive=4, neutral=1, negative=1)
    rows = _rows(
        (MATCHING_TEXT, 5, "positive"),
        (NEUTRAL_TEXT, 4, "positive"),
        (NEUTRAL_TEXT, 4, "positive"),
        (NEUTRAL_TEXT, 5, "positive"),
        (NEUTRAL_TEXT, 3, "neutral"),
        (NEUTRAL_TEXT, 1, "negative"),
    )
    result = _analyze(stats, rows)

    # Actual analyzed sample vs available pool are separate, truthful values.
    assert result.total_analyzed_reviews == 6
    assert result.review_volume == 120

    theme = next(p for p in result.pros if p.theme == "Product Performance & Reliability")
    # Documented formula: raw(1) * (120 / 6) = 20; percentage denominator is
    # the full pool: 20 / 120 = 16.7%.
    assert theme.review_count == 20
    assert theme.percentage == 16.7

    # The provenance signals describe the sample/pool distinction truthfully.
    joined = " ".join(result.authenticity_signals)
    assert "sampled 6 of 120" in joined
    assert "projections onto the full pool" in joined


def test_no_unsupported_authenticity_or_correlation_claims():
    stats = _stats(total=1, average_rating=5.0, positive=1, neutral=0, negative=0)
    rows = _rows((MATCHING_TEXT, 5, "positive"))
    result = _analyze(stats, rows)

    joined = " ".join(result.authenticity_signals)
    for claim in UNSUPPORTED_CLAIMS:
        assert claim not in joined
    # What remains is backed by the actual computation.
    assert "Average rating: 5.0 / 5.0 across 1 dataset reviews." in joined
    assert "100.0% positive" in joined


def test_summary_text_never_invents_themes_when_none_matched():
    stats = _stats(total=6, average_rating=4.0, positive=4, neutral=1, negative=1)
    rows = _rows(
        (NEUTRAL_TEXT, 5, "positive"),
        (NEUTRAL_TEXT, 4, "positive"),
        (NEUTRAL_TEXT, 4, "positive"),
        (NEUTRAL_TEXT, 5, "positive"),
        (NEUTRAL_TEXT, 3, "neutral"),
        (NEUTRAL_TEXT, 1, "negative"),
    )
    result = _analyze(stats, rows)

    # Previously the summary invented "its performance" / "minor durability
    # concerns" when no theme matched.
    assert "its performance" not in result.summary
    assert "minor durability concerns" not in result.summary
    assert "No recurring positive themes were matched" in result.summary
    assert "No recurring negative themes were matched" in result.summary
