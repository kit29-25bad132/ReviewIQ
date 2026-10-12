"""Phase 5B — aspect extraction tests.

Two layers:
* grounding is pure, so it is tested exhaustively offline — these tests prove
  that invented aspects, invented review ids, paraphrased quotes, and
  unmentioned aspects are all dropped;
* the extraction pipeline is exercised against the REAL P12 corpus with only
  the model call patched, proving grounded output cites reviews that exist.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values

from models.intelligence import EvidenceItem
from services.intelligence import aspects as aspects_module
from services.intelligence.aspects import (
    MAX_ASPECTS,
    EXTRACTION_ATTEMPTS,
    AspectExtraction,
    AspectExtractionItem,
    count_mentions,
    extract_aspects,
    ground_aspects,
)
from services.intelligence.corpus import load_product_corpus

P12 = "P12"


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    dsn = dotenv_values(env_path).get("DATABASE_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def _reviews():
    _, reviews = load_product_corpus(P12)
    return reviews


def _corpus_rows():
    """Hand-built corpus for pure grounding tests (no DB, no AI)."""
    return [
        {
            "source_review_id": "R00001",
            "review_text": "The build quality turned out superb.",
            "rating": 2,
            "sentiment": "positive",
        },
        {
            "source_review_id": "R00002",
            "review_text": "Battery life is outstanding and build quality is solid.",
            "rating": 5,
            "sentiment": "positive",
        },
        {
            "source_review_id": "R00003",
            "review_text": "Terrible battery drain after the update.",
            "rating": 1,
            "sentiment": "negative",
        },
    ]


def _item(name="battery", review_id="R00002", excerpt="Battery life is outstanding"):
    return AspectExtractionItem(
        aspect_name=name,
        sentiment="mixed",
        quote_review_id=review_id,
        quote_excerpt=excerpt,
    )


# ---------------------------------------------------------------- grounding


def test_grounding_keeps_a_traceable_aspect_and_counts_real_mentions():
    result = ground_aspects(AspectExtraction(aspects=[_item()]), _corpus_rows())
    assert len(result) == 1
    aspect = result[0]
    assert aspect.aspect_name == "battery"
    assert aspect.mention_count == 2  # R00002 and R00003 mention "battery"
    assert aspect.representative_quote.review_id == "R00002"
    assert aspect.representative_quote.excerpt == "Battery life is outstanding"


def test_grounding_drops_unknown_review_id():
    result = ground_aspects(
        AspectExtraction(aspects=[_item(review_id="R99999")]), _corpus_rows()
    )
    assert result == []


def test_grounding_drops_paraphrased_quote():
    result = ground_aspects(
        AspectExtraction(aspects=[_item(excerpt="the battery is great")]), _corpus_rows()
    )
    assert result == []


def test_grounding_drops_aspect_no_real_review_mentions():
    result = ground_aspects(
        AspectExtraction(
            aspects=[
                AspectExtractionItem(
                    aspect_name="holographic display",
                    sentiment="positive",
                    quote_review_id="R00002",
                    quote_excerpt="Battery life is outstanding",
                )
            ]
        ),
        _corpus_rows(),
    )
    assert result == []


def test_grounding_matches_quote_across_whitespace_and_case():
    review = _corpus_rows()[0]
    result = ground_aspects(
        AspectExtraction(
            aspects=[
                AspectExtractionItem(
                    aspect_name="build quality",
                    sentiment="positive",
                    quote_review_id=review["source_review_id"],
                    quote_excerpt="THE BUILD   quality TURNED OUT superb.",
                )
            ]
        ),
        _corpus_rows(),
    )
    assert len(result) == 1
    assert result[0].mention_count == 2  # R00001 and R00002 mention build quality


def test_grounding_deduplicates_aspects_case_insensitively():
    result = ground_aspects(
        AspectExtraction(aspects=[_item(), _item(name="Battery")]), _corpus_rows()
    )
    assert len(result) == 1


def test_grounding_caps_the_number_of_aspects():
    corpus = [
        {
            "source_review_id": f"RX{i}",
            "review_text": f"alpha{i} beta gamma delta epsilon",
            "rating": 4,
            "sentiment": "positive",
        }
        for i in range(MAX_ASPECTS + 4)
    ]
    items = [
        AspectExtractionItem(
            aspect_name=f"alpha{i}",
            sentiment="positive",
            quote_review_id=f"RX{i}",
            quote_excerpt=f"alpha{i} beta",
        )
        for i in range(MAX_ASPECTS + 4)
    ]
    result = ground_aspects(AspectExtraction(aspects=items), corpus)
    assert len(result) == MAX_ASPECTS


def test_grounding_orders_by_mention_count_descending():
    corpus = [
        {"source_review_id": "R1", "review_text": "battery battery", "sentiment": "positive"},
        {"source_review_id": "R2", "review_text": "battery screen", "sentiment": "positive"},
        {"source_review_id": "R3", "review_text": "screen screen", "sentiment": "positive"},
    ]
    result = ground_aspects(
        AspectExtraction(
            aspects=[
                AspectExtractionItem(
                    aspect_name="screen",
                    sentiment="positive",
                    quote_review_id="R3",
                    quote_excerpt="screen screen",
                ),
                AspectExtractionItem(
                    aspect_name="battery",
                    sentiment="mixed",
                    quote_review_id="R1",
                    quote_excerpt="battery battery",
                ),
            ]
        ),
        corpus,
    )
    assert [a.aspect_name for a in result] == ["battery", "screen"]
    assert [a.mention_count for a in result] == [2, 2]


def test_count_mentions_is_zero_when_absent():
    assert count_mentions(["battery"], ["nothing relevant here"]) == 0


# ------------------------------------------------------------------ pipeline


def test_extract_aspects_grounds_against_the_real_corpus():
    reviews = _reviews()
    target = next(r for r in reviews if "battery" in r["review_text"].lower())
    excerpt = target["review_text"][:40]

    extraction = AspectExtraction(
        aspects=[
            AspectExtractionItem(
                aspect_name="battery",
                sentiment="mixed",
                quote_review_id=target["source_review_id"],
                quote_excerpt=excerpt,
            )
        ]
    )

    with patch.object(
        aspects_module, "_attempt_extraction", return_value=extraction
    ):
        result = extract_aspects(P12)

    assert len(result) == 1
    citation = result[0].representative_quote
    real_ids = {r["source_review_id"] for r in reviews}
    real_texts = {r["review_text"] for r in reviews}
    assert citation.review_id in real_ids
    # The excerpt is a verbatim substring of a real stored review.
    assert any(citation.excerpt in text for text in real_texts)
    assert result[0].mention_count >= 1


def test_extract_aspects_drops_an_invented_citation():
    reviews = _reviews()
    target = reviews[0]

    extraction = AspectExtraction(
        aspects=[
            AspectExtractionItem(
                aspect_name="battery",
                sentiment="positive",
                quote_review_id="R99999",
                quote_excerpt=target["review_text"][:30],
            )
        ]
    )

    with patch.object(
        aspects_module, "_attempt_extraction", return_value=extraction
    ):
        assert extract_aspects(P12) == []


def test_extract_aspects_retries_once_then_returns_empty_list():
    with patch.object(aspects_module, "_try_extraction", return_value=None) as mocked:
        result = extract_aspects(P12)
    assert result == []
    assert mocked.call_count == EXTRACTION_ATTEMPTS


def test_extract_aspects_returns_empty_when_validation_keeps_failing():
    with patch.object(
        aspects_module, "_attempt_extraction", side_effect=ValueError("invalid JSON")
    ):
        assert extract_aspects(P12) == []


def test_extract_aspects_returns_empty_for_unknown_product():
    assert extract_aspects("NONEXISTENT_99999") == []


def test_extract_aspects_returns_empty_when_ai_is_not_configured(monkeypatch):
    monkeypatch.setattr(
        aspects_module.analyzer_service, "is_configured", lambda: False
    )
    assert extract_aspects(P12) == []


def test_evidence_item_rejects_empty_excerpt():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        EvidenceItem(review_id="R00001", excerpt="")
