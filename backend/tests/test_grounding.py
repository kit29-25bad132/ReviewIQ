"""Phase 2 tests: deterministic evidence grounding against the original review.

Covers:
- Exact, normalized, case, whitespace, and punctuation supported evidence.
- Fabricated, partially fabricated, and false-positive evidence rejected.
- Grounding applied to pros, cons, and aspects.
- Mixed supported/unsupported items: only unsupported items removed.
- Empty/whitespace evidence never grounded.
- Claim (point) policy: points are not substring-validated.
- Offline analyzer integration: Gemini output -> Pydantic -> grounding.

V1 behavior under test: unsupported evidence-backed items are removed
entirely from the analysis; supported items are kept unchanged; no evidence
is invented, rewritten, or replaced.
"""

import json
import sys

import pytest

from models.review import ReviewAnalysis
from services.ai_analyzer import analyzer_service
from services.grounding_service import (
    ground_analysis,
    is_evidence_supported,
    normalize_text,
)
from tests.test_model_configuration import _FakeResponse, _install_fake_sdk


def make_analysis(**overrides):
    base = {
        "sentiment": "positive",
        "rating": 4,
        "rating_source": "inferred",
        "summary": "A concise summary.",
        "aspects": [],
        "pros": [],
        "cons": [],
    }
    base.update(overrides)
    return ReviewAnalysis.model_validate(base)


REVIEW = "The battery lasts all day."


# ---------------------------------------------------------------------------
# Supported evidence (1-5)
# ---------------------------------------------------------------------------

def test_exact_supported_evidence_accepted():
    assert is_evidence_supported(REVIEW, "The battery lasts all day.") is True


def test_normalized_supported_evidence_accepted():
    assert is_evidence_supported(REVIEW, "battery lasts all day") is True


def test_case_variation_accepted():
    assert is_evidence_supported(REVIEW, "BATTERY LASTS ALL DAY") is True


def test_whitespace_and_newline_variation_accepted():
    review = "The battery   lasts\nall day."
    evidence = "The battery lasts all day."
    assert is_evidence_supported(review, evidence) is True
    evidence_with_newlines = "The  battery\nlasts   all day."
    assert is_evidence_supported(review, evidence_with_newlines) is True


def test_punctuation_variation_accepted():
    review = "The battery lasts all day."
    # Evidence omits the trailing period
    assert is_evidence_supported(review, "battery lasts all day") is True
    # Evidence uses a hyphen instead of nothing meaningful / different marks
    review2 = "It's easy-to-use and works well."
    assert is_evidence_supported(review2, "It's easy to use and works well") is True


def test_quote_and_apostrophe_variation_accepted():
    review = "It's the best phone I've bought."
    evidence_curly = "It\u2019s the best phone I\u2019ve bought"
    assert is_evidence_supported(review, evidence_curly) is True


# ---------------------------------------------------------------------------
# Unsupported evidence (6-9)
# ---------------------------------------------------------------------------

def test_fabricated_evidence_rejected():
    assert is_evidence_supported(REVIEW, "The battery lasts two days.") is False


def test_partially_fabricated_evidence_rejected():
    evidence = "The battery lasts all day and charges in 30 minutes."
    assert is_evidence_supported(REVIEW, evidence) is False


def test_false_positive_guard_shared_keyword_not_enough():
    review = "The battery lasts all day, but the camera is disappointing."
    evidence = "The battery is excellent."
    assert is_evidence_supported(review, evidence) is False


def test_unsupported_added_content_rejected():
    review = "The phone is expensive."
    evidence = "The phone is very expensive and has terrible battery life."
    assert is_evidence_supported(review, evidence) is False


def test_keyword_alone_does_not_grant_support():
    review = "The battery lasts all day, but the camera is disappointing."
    # "camera" appears in the review, but this exact claim does not
    assert is_evidence_supported(review, "The camera takes professional photos.") is False


# ---------------------------------------------------------------------------
# Grounding applied to pros / cons / aspects (10-12)
# ---------------------------------------------------------------------------

def test_grounding_applied_to_pros():
    analysis = make_analysis(pros=[
        {"point": "Good battery", "evidence": "The battery lasts all day."},
        {"point": "Amazing camera", "evidence": "The camera takes amazing photos."},
    ])
    grounded = ground_analysis(REVIEW, analysis)
    assert len(grounded.pros) == 1
    assert grounded.pros[0].point == "Good battery"
    assert grounded.pros[0].evidence == "The battery lasts all day."


def test_grounding_applied_to_cons():
    review = "The phone is expensive."
    analysis = make_analysis(cons=[
        {"point": "Pricey", "evidence": "The phone is expensive."},
        {"point": "Bad screen", "evidence": "The screen cracked instantly."},
    ])
    grounded = ground_analysis(review, analysis)
    assert len(grounded.cons) == 1
    assert grounded.cons[0].point == "Pricey"


def test_grounding_applied_to_aspects():
    analysis = make_analysis(aspects=[
        {
            "aspect": "battery",
            "sentiment": "positive",
            "evidence": "The battery lasts all day.",
        },
        {
            "aspect": "camera",
            "sentiment": "positive",
            "evidence": "The camera is stunning in low light.",
        },
    ])
    grounded = ground_analysis(REVIEW, analysis)
    assert len(grounded.aspects) == 1
    assert grounded.aspects[0].aspect == "battery"


# ---------------------------------------------------------------------------
# Multiple items / coexistence (13)
# ---------------------------------------------------------------------------

def test_supported_and_unsupported_coexist_only_unsupported_removed():
    review = "The battery lasts all day, but the camera is disappointing."
    analysis = make_analysis(
        pros=[
            {"point": "Good battery", "evidence": "The battery lasts all day."},
            {"point": "Amazing camera", "evidence": "The camera takes amazing photos."},
        ],
        cons=[
            {"point": "Disappointing camera", "evidence": "the camera is disappointing."},
            {"point": "Awful software", "evidence": "The software crashes daily."},
        ],
        aspects=[
            {"aspect": "battery", "sentiment": "positive", "evidence": "the battery lasts all day"},
            {"aspect": "camera", "sentiment": "negative", "evidence": "best camera ever"},
        ],
    )
    grounded = ground_analysis(review, analysis)
    assert [p.point for p in grounded.pros] == ["Good battery"]
    assert [c.point for c in grounded.cons] == ["Disappointing camera"]
    assert [a.aspect for a in grounded.aspects] == ["battery"]
    # All other fields unchanged
    assert grounded.sentiment == analysis.sentiment
    assert grounded.rating == analysis.rating
    assert grounded.rating_source == analysis.rating_source
    assert grounded.summary == analysis.summary


def test_all_unsupported_leaves_empty_lists_valid_contract():
    analysis = make_analysis(
        pros=[{"point": "X", "evidence": "fabricated claim not in review"}],
        cons=[{"point": "Y", "evidence": "another fabricated claim"}],
    )
    grounded = ground_analysis(REVIEW, analysis)
    assert grounded.pros == []
    assert grounded.cons == []
    # Contract remains valid (empty lists are allowed defaults)
    ReviewAnalysis.model_validate(grounded.model_dump())


# ---------------------------------------------------------------------------
# Empty / whitespace evidence (14)
# ---------------------------------------------------------------------------

def test_empty_evidence_never_grounded():
    assert is_evidence_supported(REVIEW, "") is False
    analysis = make_analysis(pros=[{"point": "Something", "evidence": ""}])
    grounded = ground_analysis(REVIEW, analysis)
    assert grounded.pros == []


def test_whitespace_only_evidence_never_grounded():
    assert is_evidence_supported(REVIEW, "   \n\t  ") is False
    analysis = make_analysis(aspects=[
        {"aspect": "battery", "sentiment": "positive", "evidence": "   "}
    ])
    grounded = ground_analysis(REVIEW, analysis)
    assert grounded.aspects == []


# ---------------------------------------------------------------------------
# Claim / point policy (Section 9)
# ---------------------------------------------------------------------------

def test_concise_point_not_literal_substring_is_kept():
    # point summarizes evidence; it is NOT substring-validated
    analysis = make_analysis(pros=[
        {"point": "Long battery life", "evidence": "The battery lasts all day."}
    ])
    grounded = ground_analysis(REVIEW, analysis)
    assert len(grounded.pros) == 1
    assert grounded.pros[0].point == "Long battery life"


def test_point_not_checked_when_evidence_unsupported():
    # Grounding decision is driven by evidence, not by point
    analysis = make_analysis(pros=[
        {"point": "Long battery life", "evidence": "The battery lasts two weeks."}
    ])
    grounded = ground_analysis(REVIEW, analysis)
    assert grounded.pros == []


# ---------------------------------------------------------------------------
# Normalization helper sanity
# ---------------------------------------------------------------------------

def test_normalize_text_collapses_and_casefolds():
    assert normalize_text("  The   battery\nlasts\tall day.  ") == "the battery lasts all day"
    assert normalize_text("") == ""


# ---------------------------------------------------------------------------
# Analyzer integration (Section 13): Gemini output -> Pydantic -> grounding
# ---------------------------------------------------------------------------

def test_analyzer_runs_grounding_offline(monkeypatch):
    """Fake Gemini returns one supported and one fabricated pro; the analyzer
    must return only the grounded pro. No network calls."""
    fake_payload = {
        "sentiment": "positive",
        "rating": 4,
        "rating_source": "inferred",
        "summary": "ok",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive", "evidence": "The battery lasts all day."},
            {"aspect": "camera", "sentiment": "positive", "evidence": "Incredible camera system."},
        ],
        "pros": [
            {"point": "Good battery", "evidence": "The battery lasts all day."},
            {"point": "Amazing camera", "evidence": "The camera takes amazing photos."},
        ],
        "cons": [
            {"point": "Pricey", "evidence": "Way too expensive for what it is."},
        ],
    }
    attempts = []
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(_FakeResponse, "text", json.dumps(fake_payload))
    _install_fake_sdk(monkeypatch, attempts)

    review_text = "The battery lasts all day."
    result = analyzer_service._call_google_genai(review_text)

    assert isinstance(result, ReviewAnalysis)
    # Supported evidence kept
    assert [p.point for p in result.pros] == ["Good battery"]
    assert [a.aspect for a in result.aspects] == ["battery"]
    # Fabricated evidence removed, never returned
    assert all("camera" not in p.evidence.lower() for p in result.pros)
    assert result.cons == []
    # Non-evidence fields pass through untouched
    assert result.rating == 4
    assert result.rating_source == "inferred"
    assert result.summary == "ok"
    assert attempts  # fake SDK was actually invoked


def test_analyzer_grounding_not_bypassed_by_empty_lists(monkeypatch):
    """Integration sanity: fully grounded output passes through unchanged."""
    fake_payload = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "explicit",
        "summary": "ok",
        "aspects": [],
        "pros": [{"point": "Good battery", "evidence": "The battery lasts all day."}],
        "cons": [],
    }
    attempts = []
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(_FakeResponse, "text", json.dumps(fake_payload))
    _install_fake_sdk(monkeypatch, attempts)

    result = analyzer_service._call_google_genai(REVIEW)
    assert len(result.pros) == 1
    assert result.pros[0].evidence == "The battery lasts all day."
