"""Phase 5F — contract enforcement tests.

Offline tests prove each invariant is actually enforced (not merely declared);
one live test proves real 5A statistics satisfy the 5F contract unchanged.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError

from models.intelligence import (
    AnalysisErrorResponse,
    AspectResult,
    ClaimWithEvidence,
    DateRange,
    EvidenceItem,
    ProductAnalysisResponse,
    ProductStatistics,
    filter_evidence_backed_claims,
    validate_analysis_response,
)


def _statistics(**overrides) -> ProductStatistics:
    payload = {
        "total_reviews": 10,
        "average_rating": 4.0,
        "rating_distribution": {1: 1, 2: 1, 3: 2, 4: 3, 5: 3},
        "sentiment_distribution": {"positive": 6, "neutral": 3, "negative": 1},
        "verified_purchase_pct": 100.0,
        "date_range": DateRange(earliest="2024-10-12", latest="2026-09-25"),
    }
    payload.update(overrides)
    return ProductStatistics(**payload)


def _response(**overrides) -> ProductAnalysisResponse:
    payload = {
        "product_id": "P12",
        "product_name": "Kelto Gamer 16",
        "statistics": _statistics(),
        "aspects": [
            AspectResult(
                aspect_name="battery",
                sentiment="positive",
                mention_count=4,
                representative_quote=EvidenceItem(review_id="R00005", excerpt="battery"),
            )
        ],
        "pros": [
            ClaimWithEvidence(
                claim="Battery lasts two days",
                evidence=[EvidenceItem(review_id="R00005", excerpt="battery life")],
                support_count=1,
            )
        ],
        "cons": [],
        "summary": "Customers praise battery life.",
        "best_for": "Best for commuters who need two-day battery life.",
        "data_source": "supabase",
        "review_count_used": 10,
        "generated_at": datetime.now(timezone.utc),
    }
    payload.update(overrides)
    return ProductAnalysisResponse(**payload)


def test_valid_payload_round_trips():
    response = _response()
    assert response.product_id == "P12"
    assert response.statistics.total_reviews == 10
    assert response.data_source == "supabase"


def test_claim_without_evidence_is_rejected():
    with pytest.raises(ValidationError):
        ClaimWithEvidence(claim="Great battery", evidence=[], support_count=1)


def test_claim_support_count_must_be_at_least_one():
    with pytest.raises(ValidationError):
        ClaimWithEvidence(
            claim="Great battery",
            evidence=[EvidenceItem(review_id="R00005", excerpt="battery")],
            support_count=0,
        )


def test_evidence_item_requires_non_empty_fields():
    with pytest.raises(ValidationError):
        EvidenceItem(review_id="", excerpt="battery")
    with pytest.raises(ValidationError):
        EvidenceItem(review_id="R00005", excerpt="")


def test_aspect_sentiment_must_be_positive_negative_or_mixed():
    with pytest.raises(ValidationError):
        AspectResult(
            aspect_name="battery",
            sentiment="neutral",
            mention_count=2,
            representative_quote=EvidenceItem(review_id="R00005", excerpt="battery"),
        )


def test_aspect_requires_at_least_one_mention():
    with pytest.raises(ValidationError):
        AspectResult(
            aspect_name="battery",
            sentiment="positive",
            mention_count=0,
            representative_quote=EvidenceItem(review_id="R00005", excerpt="battery"),
        )


def test_rating_distribution_must_sum_to_total_reviews():
    with pytest.raises(ValidationError):
        _statistics(rating_distribution={1: 1, 2: 1, 3: 2, 4: 3, 5: 99})


def test_sentiment_distribution_must_sum_to_total_reviews():
    with pytest.raises(ValidationError):
        _statistics(sentiment_distribution={"positive": 1, "neutral": 1, "negative": 1})


def test_rating_distribution_requires_exactly_the_five_star_keys():
    # Missing the 5 star bucket (still sums to 10) -> invalid.
    with pytest.raises(ValidationError):
        _statistics(rating_distribution={1: 2, 2: 2, 3: 2, 4: 4}, total_reviews=10)
    # An out-of-range bucket (still sums to 10) -> invalid.
    with pytest.raises(ValidationError):
        _statistics(
            rating_distribution={1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 5},
            total_reviews=10,
        )


def test_average_rating_must_be_rounded_to_one_decimal_place():
    with pytest.raises(ValidationError):
        _statistics(average_rating=3.55)
    assert _statistics(average_rating=3.5).average_rating == 3.5


def test_verified_purchase_pct_bounds():
    with pytest.raises(ValidationError):
        _statistics(verified_purchase_pct=100.1)
    with pytest.raises(ValidationError):
        _statistics(verified_purchase_pct=-0.1)


def test_date_range_rejects_reversed_bounds():
    with pytest.raises(ValidationError):
        DateRange(earliest="2026-09-25", latest="2024-10-12")


def test_review_count_used_cannot_exceed_total_reviews():
    with pytest.raises(ValidationError):
        _response(review_count_used=11)


def test_ai_unavailable_requires_empty_ai_fields():
    with pytest.raises(ValidationError):
        _response(ai_unavailable=True)
    empty = _response(
        ai_unavailable=True,
        aspects=[],
        pros=[],
        cons=[],
        summary="Insufficient reviews",
        best_for="",
    )
    assert empty.ai_unavailable is True


def test_data_source_must_be_supabase():
    with pytest.raises(ValidationError):
        _response(data_source="sqlite")


def test_rating_distribution_is_int_keyed_in_python_and_string_keyed_in_json():
    """JSON mandates string keys; the Python model keeps int keys."""
    stats = _statistics()
    assert sorted(stats.rating_distribution.keys()) == [1, 2, 3, 4, 5]
    assert all(isinstance(k, int) for k in stats.model_dump()["rating_distribution"])

    wire = json.loads(stats.model_dump_json())["rating_distribution"]
    assert sorted(wire.keys()) == ["1", "2", "3", "4", "5"]


def test_validate_analysis_response_returns_structured_error_instead_of_raising():
    result = validate_analysis_response({"product_id": "P12"})
    assert isinstance(result, AnalysisErrorResponse)
    assert result.code == "validation_error"
    assert result.error


def test_validate_analysis_response_accepts_a_valid_payload():
    result = validate_analysis_response(_response().model_dump())
    assert isinstance(result, ProductAnalysisResponse)


def test_filter_evidence_backed_claims_drops_untraceable_claims():
    traceable = ClaimWithEvidence(
        claim="Battery lasts two days",
        evidence=[EvidenceItem(review_id="R00005", excerpt="battery life")],
        support_count=1,
    )
    invented = ClaimWithEvidence(
        claim="Has a 4K OLED screen",
        evidence=[EvidenceItem(review_id="R99999", excerpt="screen")],
        support_count=1,
    )
    kept = filter_evidence_backed_claims([traceable, invented], {"R00005"})
    assert [c.claim for c in kept] == ["Battery lasts two days"]


def test_filter_evidence_backed_claims_drops_claim_if_any_citation_is_unknown():
    mixed = ClaimWithEvidence(
        claim="Mixed evidence",
        evidence=[
            EvidenceItem(review_id="R00005", excerpt="battery"),
            EvidenceItem(review_id="R99999", excerpt="ghost"),
        ],
        support_count=2,
    )
    assert filter_evidence_backed_claims([mixed], {"R00005"}) == []


def test_real_5a_statistics_satisfy_the_5f_contract(monkeypatch):
    """The live 5A engine output must validate against 5F unchanged."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    dsn = dotenv_values(env_path).get("DATABASE_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)

    from services.catalog.catalog_service import canonical_catalog

    if not canonical_catalog.is_configured():
        pytest.skip("live Supabase DSN not configured")

    from services.intelligence.statistics import compute_statistics

    real = compute_statistics("P12")
    assert real is not None

    contract = ProductStatistics(
        total_reviews=real.total_reviews,
        average_rating=real.average_rating,
        rating_distribution=real.rating_distribution,
        sentiment_distribution=real.sentiment_distribution,
        verified_purchase_pct=real.verified_purchase_pct,
        date_range=DateRange(
            earliest=real.date_range.earliest, latest=real.date_range.latest
        ),
    )
    assert contract.total_reviews == 95
    assert sum(contract.rating_distribution.values()) == 95
    assert sum(contract.sentiment_distribution.values()) == 95
