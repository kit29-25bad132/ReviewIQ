"""Gate 2 (Phase 4): pros/cons evidence integrity.

Uses an in-memory SQLite database (no writes to any real database, no live
providers). Proves that:
- fabricated fallback quotations can never be returned;
- evidence quotes trace to actual source reviews;
- the analyzed sample size is distinguished from the available review pool;
- projected counts follow the documented formula and denominator;
- unsupported authenticity/correlation claims are absent.
"""

import sqlite3
from unittest.mock import patch

from services.ecommerce_db_service import ecommerce_db_service
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


def _make_connection(products, reviews):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE products (
            product_id TEXT, product_title TEXT, category TEXT,
            review_count INTEGER, average_rating REAL,
            positive_count INTEGER, neutral_count INTEGER, negative_count INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY, product_id TEXT, review_text TEXT,
            rating INTEGER, sentiment TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", products
    )
    conn.executemany(
        "INSERT INTO reviews (product_id, review_text, rating, sentiment) VALUES (?, ?, ?, ?)",
        reviews,
    )
    conn.commit()
    return conn


def _analyze(products, reviews):
    conn = _make_connection(products, reviews)
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "_get_connection", return_value=conn
    ):
        return pros_cons_service.analyze_product_pros_cons("P1")


def test_no_fabricated_fallback_quotes_when_no_theme_matches():
    # 6 real reviews, none matching any theme keyword; product has real
    # positive/negative counts so the fallback aggregate themes appear.
    products = [("P1", "Selected Product", "Category", 6, 4.0, 4, 1, 1)]
    reviews = [
        ("P1", NEUTRAL_TEXT, 5, "positive"),
        ("P1", NEUTRAL_TEXT, 4, "positive"),
        ("P1", NEUTRAL_TEXT, 4, "positive"),
        ("P1", NEUTRAL_TEXT, 5, "positive"),
        ("P1", NEUTRAL_TEXT, 3, "neutral"),
        ("P1", NEUTRAL_TEXT, 1, "negative"),
    ]
    result = _analyze(products, reviews)
    payload = result.model_dump_json()

    for quote in FABRICATED_QUOTES:
        assert quote not in payload
    for claim in UNSUPPORTED_CLAIMS:
        assert claim not in payload

    # Fallback themes exist but carry NO evidence quotes, since no source
    # review supports a specific theme.
    assert result.pros[0].theme == "Overall Customer Satisfaction"
    assert result.pros[0].example_reviews == []
    assert result.pros[0].evidence_review_ids == []
    assert result.cons[0].theme == "General Customer Dissatisfaction"
    assert result.cons[0].example_reviews == []


def test_evidence_quotes_trace_to_actual_source_reviews():
    products = [("P1", "Selected Product", "Category", 1, 5.0, 1, 0, 0)]
    reviews = [("P1", MATCHING_TEXT, 5, "positive")]
    result = _analyze(products, reviews)

    assert result.pros
    theme = next(p for p in result.pros if p.theme == "Product Performance & Reliability")
    # The evidence quote is verbatim a real review row, not a template.
    assert theme.example_reviews == [MATCHING_TEXT]
    assert theme.evidence_review_ids == [1]


def test_sample_size_is_distinguished_from_available_pool_and_projection_is_documented():
    # Only 6 reviews exist to analyze, but the product's full pool is 120.
    products = [("P1", "Selected Product", "Category", 120, 4.0, 4, 1, 1)]
    reviews = [
        ("P1", MATCHING_TEXT, 5, "positive"),
        ("P1", NEUTRAL_TEXT, 4, "positive"),
        ("P1", NEUTRAL_TEXT, 4, "positive"),
        ("P1", NEUTRAL_TEXT, 5, "positive"),
        ("P1", NEUTRAL_TEXT, 3, "neutral"),
        ("P1", NEUTRAL_TEXT, 1, "negative"),
    ]
    result = _analyze(products, reviews)

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
    products = [("P1", "Selected Product", "Category", 1, 5.0, 1, 0, 0)]
    reviews = [("P1", MATCHING_TEXT, 5, "positive")]
    result = _analyze(products, reviews)

    joined = " ".join(result.authenticity_signals)
    for claim in UNSUPPORTED_CLAIMS:
        assert claim not in joined
    # What remains is backed by the actual computation.
    assert "Average rating: 5.0 / 5.0 across 1 dataset reviews." in joined
    assert "100.0% positive" in joined


def test_summary_text_never_invents_themes_when_none_matched():
    products = [("P1", "Selected Product", "Category", 6, 4.0, 4, 1, 1)]
    reviews = [
        ("P1", NEUTRAL_TEXT, 5, "positive"),
        ("P1", NEUTRAL_TEXT, 4, "positive"),
        ("P1", NEUTRAL_TEXT, 4, "positive"),
        ("P1", NEUTRAL_TEXT, 5, "positive"),
        ("P1", NEUTRAL_TEXT, 3, "neutral"),
        ("P1", NEUTRAL_TEXT, 1, "negative"),
    ]
    result = _analyze(products, reviews)

    # Previously the summary invented "its performance" / "minor durability
    # concerns" when no theme matched.
    assert "its performance" not in result.summary
    assert "minor durability concerns" not in result.summary
    assert "No recurring positive themes were matched" in result.summary
    assert "No recurring negative themes were matched" in result.summary
