"""Phase 5C — pros/cons evidence tests.

* claim building is pure, so it is tested exhaustively offline: every path
  where a claim lacks traceable evidence must DROP it;
* one live test proves the pgvector RAG stage actually retrieves this
  product's real reviews (no mocks);
* the pipeline is otherwise exercised with only the model call patched.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values

from services.intelligence import pros_cons as pros_cons_module
from services.intelligence.corpus import load_product_corpus
from services.intelligence.pros_cons import (
    EXCERPT_MAX_CHARS,
    MAX_CLAIMS_PER_SIDE,
    MAX_EVIDENCE_PER_CLAIM,
    ClaimDraft,
    ClaimsDraft,
    build_claims,
    generate_pros_cons,
    intelligence_rag_enabled,
    retrieve_evidence,
)

P12 = "P12"


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    dsn = dotenv_values(env_path).get("DATABASE_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def _corpus():
    return {
        "R1": {"source_review_id": "R1", "review_text": "Battery life is superb and lasts two days."},
        "R2": {"source_review_id": "R2", "review_text": "Great value for the price."},
        "R3": {"source_review_id": "R3", "review_text": ""},
    }


# ------------------------------------------------------------- build_claims


def test_keeps_claim_with_resolvable_evidence_and_counts_citations():
    claims = build_claims(
        [ClaimDraft(claim="Battery lasts two days", evidence_review_ids=["R1", "R2"])],
        _corpus(),
    )
    assert len(claims) == 1
    assert claims[0].support_count == 2
    assert [e.review_id for e in claims[0].evidence] == ["R1", "R2"]


def test_excerpts_are_verbatim_slices_of_real_review_text():
    claims = build_claims(
        [ClaimDraft(claim="Battery", evidence_review_ids=["R1"])], _corpus()
    )
    excerpt = claims[0].evidence[0].excerpt
    assert excerpt in _corpus()["R1"]["review_text"]
    assert len(excerpt) <= EXCERPT_MAX_CHARS


def test_excerpt_prefers_the_sentence_that_supports_the_claim():
    corpus = {
        "R1": {
            "source_review_id": "R1",
            "review_text": "The box was fine. Honestly the keyboard is mushy and hard to type on. Shipping was fast.",
        }
    }
    claims = build_claims(
        [ClaimDraft(claim="Keyboard is mushy", evidence_review_ids=["R1"])], corpus
    )
    excerpt = claims[0].evidence[0].excerpt
    assert excerpt in corpus["R1"]["review_text"]
    assert "keyboard is mushy" in excerpt.lower()


def test_excerpt_falls_back_to_leading_text_when_nothing_overlaps():
    corpus = {
        "R1": {
            "source_review_id": "R1",
            "review_text": "First sentence here. Second sentence follows.",
        }
    }
    claims = build_claims(
        [ClaimDraft(claim="zzzqqq", evidence_review_ids=["R1"])], corpus
    )
    assert claims[0].evidence[0].excerpt == "First sentence here. Second sentence follows."


def test_drops_claim_with_no_resolvable_evidence():
    claims = build_claims(
        [ClaimDraft(claim="Has a 4K OLED panel", evidence_review_ids=["R99999"])],
        _corpus(),
    )
    assert claims == []


def test_drops_claim_with_no_evidence_ids_at_all():
    assert build_claims([ClaimDraft(claim="Amazing", evidence_review_ids=[])], _corpus()) == []


def test_keeps_claim_and_prunes_unresolvable_citations():
    claims = build_claims(
        [ClaimDraft(claim="Good value", evidence_review_ids=["R99999", "R2"])], _corpus()
    )
    assert len(claims) == 1
    assert [e.review_id for e in claims[0].evidence] == ["R2"]
    assert claims[0].support_count == 1


def test_drops_claim_whose_only_review_has_no_usable_text():
    claims = build_claims([ClaimDraft(claim="Empty", evidence_review_ids=["R3"])], _corpus())
    assert claims == []


def test_deduplicates_claims_case_insensitively():
    claims = build_claims(
        [
            ClaimDraft(claim="Battery lasts two days", evidence_review_ids=["R1"]),
            ClaimDraft(claim="battery LASTS two days", evidence_review_ids=["R1"]),
        ],
        _corpus(),
    )
    assert len(claims) == 1


def test_caps_claims_and_evidence_per_claim():
    corpus = {
        f"R{i}": {"source_review_id": f"R{i}", "review_text": f"real review text {i}"}
        for i in range(MAX_EVIDENCE_PER_CLAIM + 2)
    }
    drafts = [
        ClaimDraft(claim=f"claim {i}", evidence_review_ids=list(corpus.keys()))
        for i in range(MAX_CLAIMS_PER_SIDE + 3)
    ]
    claims = build_claims(drafts, corpus)
    assert len(claims) == MAX_CLAIMS_PER_SIDE
    assert all(len(c.evidence) == MAX_EVIDENCE_PER_CLAIM for c in claims)


def test_every_returned_claim_has_at_least_one_evidence_item():
    claims = build_claims(
        [
            ClaimDraft(claim="a", evidence_review_ids=["R1"]),
            ClaimDraft(claim="b", evidence_review_ids=["R99999"]),
            ClaimDraft(claim="c", evidence_review_ids=[]),
        ],
        _corpus(),
    )
    assert claims
    assert all(len(c.evidence) >= 1 for c in claims)


# ------------------------------------------------------------ RAG enablement


def test_intelligence_rag_defaults_to_enabled(monkeypatch):
    monkeypatch.delenv("RAG_INTELLIGENCE_ENABLED", raising=False)
    assert intelligence_rag_enabled() is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off"])
def test_intelligence_rag_can_be_disabled(monkeypatch, value):
    monkeypatch.setenv("RAG_INTELLIGENCE_ENABLED", value)
    assert intelligence_rag_enabled() is False


# --------------------------------------------------------------- live RAG


def test_rag_retrieves_real_reviews_for_the_product():
    """Live pgvector search: the RAG stage must return this product's reviews."""
    results, status = retrieve_evidence(
        P12, ["What do customers complain about with the Kelto Gamer 16 laptop?"]
    )
    assert status == "ok", f"RAG status was {status!r}"
    assert results, "RAG returned no reviews"
    real_ids = {r["source_review_id"] for r in load_product_corpus(P12)[1]}
    returned = {str(r.review_id) for r in results}
    assert returned <= real_ids, "RAG returned reviews outside the product"


# ------------------------------------------------------------- pipeline


def test_generate_pros_cons_grounds_every_claim_in_the_real_corpus():
    reviews = load_product_corpus(P12)[1]
    ids = [r["source_review_id"] for r in reviews[:3]]
    draft = ClaimsDraft(
        pros=[ClaimDraft(claim="Battery life is long", evidence_review_ids=ids)],
        cons=[ClaimDraft(claim="Build quality is poor", evidence_review_ids=[ids[0]])],
    )

    with patch.object(
        pros_cons_module, "retrieve_evidence", return_value=([], "disabled")
    ), patch.object(pros_cons_module, "_attempt_claims", return_value=draft):
        pros, cons = generate_pros_cons(P12)

    real_ids = {r["source_review_id"] for r in reviews}
    real_texts = [r["review_text"] for r in reviews]
    for claim in pros + cons:
        assert claim.support_count == len(claim.evidence) >= 1
        for item in claim.evidence:
            assert item.review_id in real_ids
            assert any(item.excerpt in text for text in real_texts)
    assert len(pros) == 1 and len(cons) == 1
    assert pros[0].support_count == 3


def test_generate_pros_cons_drops_fully_invented_claims():
    draft = ClaimsDraft(
        pros=[ClaimDraft(claim="Made of titanium", evidence_review_ids=["R99999"])],
        cons=[],
    )
    with patch.object(
        pros_cons_module, "retrieve_evidence", return_value=([], "disabled")
    ), patch.object(pros_cons_module, "_attempt_claims", return_value=draft):
        pros, cons = generate_pros_cons(P12)
    assert pros == [] and cons == []


def test_generate_pros_cons_retries_the_model_twice_then_returns_empty():
    with patch.object(
        pros_cons_module, "retrieve_evidence", return_value=([], "disabled")
    ), patch.object(
        pros_cons_module, "_try_claims", return_value=None
    ) as mocked:
        pros, cons = generate_pros_cons(P12)
    assert pros == [] and cons == []
    assert mocked.call_count == 2


def test_generate_pros_cons_returns_empty_for_unknown_product():
    assert generate_pros_cons("NONEXISTENT_99999") == ([], [])


def test_generate_pros_cons_returns_empty_when_ai_not_configured(monkeypatch):
    monkeypatch.setattr(
        pros_cons_module.analyzer_service, "is_configured", lambda: False
    )
    assert generate_pros_cons(P12) == ([], [])
