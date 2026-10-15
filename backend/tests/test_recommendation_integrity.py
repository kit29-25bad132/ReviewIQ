"""Gate 2 (Phase 4): recommendation claim integrity.

Uses an in-memory SQLite database and patched peer discovery (no writes to
any real database, no live providers). Proves that:
- the selected product's metrics are associated with the correct product;
- no uncomputed peer-average claim is emitted (the average IS computed);
- ranking/confidence wording only appears when supported by a computation;
- previously unsupported phrases are gone.
"""

import sqlite3
from unittest.mock import patch

from models.ecommerce import (
    ProConTheme,
    ProsConsAnalysisResponse,
    ProductSummary,
    UserRequirementRequest,
)
from services.ecommerce_db_service import ecommerce_db_service
from services.pros_cons_service import pros_cons_service
from services.recommendation_service import recommendation_service

UNSUPPORTED_PHRASES = (
    "highest composite satisfaction score",
    "Outperforms peer average",
    "Verified strengths",
    "high rating confidence",
    "Minor complaints",
    "Minor durability concerns",
)


def _make_connection(products):
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
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", products)
    conn.commit()
    return conn


def _pros_cons_fixture():
    return ProsConsAnalysisResponse(
        product_id="P1",
        product_title="Selected Product",
        total_analyzed_reviews=6,
        pros=[
            ProConTheme(
                theme="Battery Life",
                review_count=20,
                percentage=16.7,
                example_reviews=["It works perfectly for my daily routine."],
                evidence_review_ids=[1],
            )
        ],
        cons=[],
        summary="s",
        top_pros=["Battery Life"],
        top_cons=[],
        review_volume=120,
        average_rating=4.0,
        sentiment_percentages={"positive": 50.0, "neutral": 30.0, "negative": 20.0},
        authenticity_signals=[],
        source_label="x",
    )


# P1 (selected): 4.0★, 50/30/20 of 100 -> composite 4.0*0.6 + 0.50*0.4 = 2.60
# P2 (peer):     4.5★, 80/10/10 of 100 -> composite 4.5*0.6 + 0.80*0.4 = 3.02
_PRODUCTS = [
    ("P1", "Selected Product", "Category", 100, 4.0, 50, 30, 20),
    ("P2", "Peer Product", "Category", 100, 4.5, 80, 10, 10),
]

_PEER = ProductSummary(
    product_id="P2",
    product_title="Peer Product",
    category="Category",
    review_count=100,
    average_rating=4.5,
)


def _generate(products=_PRODUCTS):
    conn = _make_connection(products)
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "_get_connection", return_value=conn
    ), patch.object(
        recommendation_service, "get_similar_products", return_value=[_PEER]
    ), patch.object(
        pros_cons_service, "analyze_product_pros_cons", return_value=_pros_cons_fixture()
    ):
        return recommendation_service.generate_recommendation(
            "P1", UserRequirementRequest(priorities=["Battery Life"])
        )


def test_negative_feedback_rate_references_the_selected_product():
    result = _generate()
    joined = " ".join(result.consider_before_buying)
    # P1's own negative rate (20.0%), not the peer's (10.0%).
    assert "Negative feedback rate for this product is 20.0%" in joined
    assert "is 10.0%" not in joined


def test_peer_average_is_actually_computed_and_stated():
    result = _generate()
    joined = " ".join(result.recommendation_reasons)
    # (4.0 + 4.5) / 2 = 4.25 across the 2 compared products.
    assert "4.25 ★ average across the 2 compared peers" in joined
    assert "Outperforms peer average" not in joined


def test_no_unsupported_ranking_or_confidence_phrases():
    result = _generate()
    payload = result.model_dump_json().lower()
    for phrase in UNSUPPORTED_PHRASES:
        assert phrase.lower() not in payload
    assert "verified" not in payload


def test_verdict_describes_the_computed_composite_measure():
    result = _generate()
    # P2 wins on the computed composite (3.02 vs 2.60), so the verdict must
    # reference the computed measure and show both sides' real numbers.
    assert "computed composite measure" in result.suitability_verdict
    assert "4.5 ★ / 80.0% positive vs 4.0 ★ / 50.0% positive" in result.suitability_verdict
    assert result.recommendation_headline.startswith("Consider 'Peer Product'")


def test_selected_product_ranking_verdict_when_it_actually_wins():
    # P1: 5.0★, 100% positive -> composite 3.40 > P2's 3.02.
    products = [
        ("P1", "Selected Product", "Category", 100, 5.0, 100, 0, 0),
        ("P2", "Peer Product", "Category", 100, 4.5, 80, 10, 10),
    ]
    result = _generate(products)
    assert "ranks highest on the computed composite score" in result.suitability_verdict
    assert result.recommendation_headline.startswith("'Selected Product'")


def test_matched_priority_reports_sample_projected_estimate():
    result = _generate()
    match = next(m for m in result.priority_matches if m.priority == "Battery Life")
    assert match.evidence_level == "Strong Evidence"
    assert "estimated ~20 reviews" in match.details
    assert "projected from a keyword sample" in match.details
    assert "(~16.7% of the product's 120 reviews;" in match.details


def test_unmatched_priority_reports_no_evidence_instead_of_fabricated_alignment():
    conn = _make_connection(_PRODUCTS)
    with patch.object(ecommerce_db_service, "is_ready", return_value=True), patch.object(
        ecommerce_db_service, "_get_connection", return_value=conn
    ), patch.object(
        recommendation_service, "get_similar_products", return_value=[_PEER]
    ), patch.object(
        pros_cons_service, "analyze_product_pros_cons", return_value=_pros_cons_fixture()
    ):
        result = recommendation_service.generate_recommendation(
            "P1", UserRequirementRequest(priorities=["Quantum Zzz"])
        )
    match = result.priority_matches[0]
    # Previously: "Moderate Evidence" + "General customer satisfaction aligns
    # with this requirement." — a fabricated alignment claim.
    assert match.evidence_level == "No Direct Evidence"
    assert "No matching review theme was found" in match.details
    assert match.supporting_reviews == []
