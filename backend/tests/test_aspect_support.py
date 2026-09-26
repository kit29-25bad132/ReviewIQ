"""V2-P8 tests: deterministic aspect evidence support (not model confidence).

Fully offline. Verifies observable behavior/invariants:
- backward-compatible aspect payloads,
- deterministic support classification (strong/moderate/weak),
- unsupported evidence can never receive strong/moderate,
- grounded evidence support correctness,
- grounding runs before classification,
- provider schema compatibility (Gemini native schema; Groq/OpenRouter JSON mode),
- RAG provenance (retrieved context cannot become aspect evidence),
- unchanged public envelopes.

Support is application-computed metadata, never an LLM score.
"""

import json

import pytest

from models.ecommerce import AISummaryResponse
from models.review import (
    AspectSentiment,
    AnalyzeReviewResponse,
    ReviewAnalysis,
)
from services.ai_analyzer import DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES
from services.grounding_service import (
    SUPPORT_MODERATE,
    SUPPORT_STRONG,
    SUPPORT_WEAK,
    classify_aspect_support,
    ground_analysis,
    is_evidence_supported,
)
from tests.test_analysis_orchestration import (
    VALID_PAYLOAD,
    _payload_text,
    _run,
)


def make_analysis(**overrides) -> ReviewAnalysis:
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


# ---------------------------------------------------------------------------
# 1-2. Backward compatibility / default
# ---------------------------------------------------------------------------

def test_pre_p8_aspect_payload_still_validates_with_null_support():
    model = ReviewAnalysis.model_validate(
        {
            "sentiment": "positive",
            "rating": 5,
            "rating_source": "inferred",
            "summary": "ok",
            "aspects": [
                {
                    "aspect": "battery",
                    "sentiment": "positive",
                    "evidence": "The battery lasts all day",
                }
            ],
            "pros": [],
            "cons": [],
        }
    )
    assert isinstance(model.aspects[0], AspectSentiment)
    # support is optional and defaults to None until grounding runs.
    assert model.aspects[0].support is None


def test_raw_contract_validation_does_not_require_support():
    aspect = AspectSentiment(
        aspect="battery", sentiment="positive", evidence="text"
    )
    assert aspect.support is None


# ---------------------------------------------------------------------------
# 3-8. Deterministic classification
# ---------------------------------------------------------------------------

def test_strong_support_for_verbatim_evidence_mentioning_aspect():
    review = "The battery lasts all day."
    grounded = ground_analysis(
        review,
        make_analysis(aspects=[
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day"}
        ]),
    )
    assert grounded.aspects[0].support == SUPPORT_STRONG


def test_moderate_support_for_normalized_only_match():
    review = "The Battery lasts all day."
    grounded = ground_analysis(
        review,
        make_analysis(aspects=[
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "the battery lasts all day"}
        ]),
    )
    # Grounded after normalization only (case differs) -> moderate.
    assert grounded.aspects[0].support == SUPPORT_MODERATE


def test_weak_support_when_evidence_omits_the_aspect():
    review = "The picture quality is great."
    grounded = ground_analysis(
        review,
        make_analysis(aspects=[
            {"aspect": "camera", "sentiment": "positive",
             "evidence": "picture quality is great"}
        ]),
    )
    # Evidence is grounded and verbatim, but never mentions the aspect.
    assert grounded.aspects[0].support == SUPPORT_WEAK


def test_unsupported_aspect_is_removed_and_cannot_carry_support():
    review = "The battery lasts all day."
    grounded = ground_analysis(
        review,
        make_analysis(aspects=[
            {"aspect": "camera", "sentiment": "negative",
             "evidence": "the camera is absolutely terrible"}
        ]),
    )
    assert grounded.aspects == []


def test_classify_returns_weak_for_unsupported_evidence():
    review = "The battery lasts all day."
    assert classify_aspect_support(review, "battery", "fabricated text") == SUPPORT_WEAK


def test_classification_is_deterministic():
    review = "The battery lasts all day."
    first = classify_aspect_support(review, "battery", "The battery lasts all day")
    second = classify_aspect_support(review, "battery", "The battery lasts all day")
    assert first == second == SUPPORT_STRONG


# ---------------------------------------------------------------------------
# 6. Duplicate evidence behavior unchanged
# ---------------------------------------------------------------------------

def test_duplicate_aspect_evidence_is_still_deduped_and_supported():
    review = "The battery lasts all day."
    grounded = ground_analysis(
        review,
        make_analysis(aspects=[
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day"},
            {"aspect": "battery life", "sentiment": "positive",
             "evidence": "The battery lasts all day"},
        ]),
    )
    assert len(grounded.aspects) == 1
    assert grounded.aspects[0].support == SUPPORT_STRONG


# ---------------------------------------------------------------------------
# 7-8. Independence + sentiment semantics unchanged
# ---------------------------------------------------------------------------

def test_multiple_aspects_remain_independent_with_correct_support():
    review = "The Battery lasts all day and the screen is dim."
    grounded = ground_analysis(
        review,
        make_analysis(aspects=[
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The Battery lasts all day"},
            {"aspect": "screen", "sentiment": "negative",
             "evidence": "the Screen is dim"},
        ]),
    )
    assert [a.aspect for a in grounded.aspects] == ["battery", "screen"]
    assert [a.support for a in grounded.aspects] == [SUPPORT_STRONG, SUPPORT_MODERATE]
    # Sentiment semantics unchanged.
    assert [a.sentiment for a in grounded.aspects] == ["positive", "negative"]


# ---------------------------------------------------------------------------
# 9. Invalid aspect payload still triggers fallback
# ---------------------------------------------------------------------------

def test_invalid_aspect_payload_still_falls_back(monkeypatch):
    malformed = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "x",
        "aspects": [{"aspect": "battery", "sentiment": "positive"}],  # no evidence
        "pros": [],
        "cons": [],
    }
    result = _run(monkeypatch, [_payload_text(malformed), _payload_text(VALID_PAYLOAD)])
    assert result.sentiment == "positive"
    assert _run.last_attempts == [DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES[0]]
    # The grounded result carries application-computed support.
    assert result.aspects[0].support in {SUPPORT_STRONG, SUPPORT_MODERATE, SUPPORT_WEAK}


# ---------------------------------------------------------------------------
# 10-12. Provider compatibility
# ---------------------------------------------------------------------------

def test_gemini_structured_schema_remains_convertible():
    from google.genai import _transformers as genai_transformers

    schema = ReviewAnalysis.model_json_schema()
    # Mirrors the SDK's native structured-output conversion; must not raise.
    genai_transformers.process_schema(schema, None, defs=schema.get("$defs"))
    support = schema["$defs"]["AspectSentiment"]["properties"]["support"]
    assert support["nullable"] is True
    assert set(support["enum"]) == {SUPPORT_STRONG, SUPPORT_MODERATE, SUPPORT_WEAK}


@pytest.mark.parametrize("provider_style", ["groq", "openrouter"])
def test_provider_style_payload_without_support_is_accepted_and_grounded(provider_style):
    # Groq/OpenRouter JSON mode: the model returns JSON without the
    # application-only support field; validation + grounding must still work.
    review = "The camera is fantastic but the battery dies quickly."
    payload = {
        "sentiment": "mixed",
        "rating": 3,
        "rating_source": "inferred",
        "summary": "Mixed experience.",
        "aspects": [
            {"aspect": "camera", "sentiment": "positive",
             "evidence": "the camera is fantastic"},
            {"aspect": "battery", "sentiment": "negative",
             "evidence": "the battery dies quickly"},
        ],
        "pros": [],
        "cons": [],
    }
    model = ReviewAnalysis.model_validate(json.loads(json.dumps(payload)))
    grounded = ground_analysis(review, model)
    assert [a.aspect for a in grounded.aspects] == ["camera", "battery"]
    assert all(a.support is not None for a in grounded.aspects)


def test_model_emitted_support_is_overwritten_by_grounding():
    review = "The picture quality is great."
    model = ReviewAnalysis.model_validate({
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "ok",
        "aspects": [
            {"aspect": "camera", "sentiment": "positive",
             "evidence": "picture quality is great", "support": "strong"}
        ],
        "pros": [],
        "cons": [],
    })
    grounded = ground_analysis(review, model)
    # Deterministic classification wins; the model value is discarded.
    assert grounded.aspects[0].support == SUPPORT_WEAK


def test_invalid_model_support_value_does_not_fail_validation():
    model = ReviewAnalysis.model_validate({
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "ok",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "text", "support": "super-high"}
        ],
        "pros": [],
        "cons": [],
    })
    assert model.aspects[0].support is None


# ---------------------------------------------------------------------------
# 13. RAG provenance: context cannot become aspect evidence
# ---------------------------------------------------------------------------

def test_retrieved_context_evidence_is_not_accepted_as_aspect_evidence():
    original_review = "The battery lasts all day."
    context_review_text = "The camera is excellent and the screen is bright."
    grounded = ground_analysis(
        original_review,
        make_analysis(aspects=[
            {"aspect": "camera", "sentiment": "positive",
             "evidence": context_review_text},
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day"},
        ]),
    )
    # Context-only aspect evidence is removed; original-review evidence survives.
    assert [a.aspect for a in grounded.aspects] == ["battery"]
    assert is_evidence_supported(original_review, grounded.aspects[0].evidence)
    assert grounded.aspects[0].evidence == "The battery lasts all day"


# ---------------------------------------------------------------------------
# 16-17. Public contracts unchanged
# ---------------------------------------------------------------------------

def test_review_analysis_top_level_contract_unchanged():
    dumped = make_analysis(pros=[], cons=[]).model_dump()
    assert set(dumped) == {
        "sentiment",
        "rating",
        "rating_source",
        "summary",
        "aspects",
        "pros",
        "cons",
    }


def test_public_response_envelope_unchanged():
    assert set(AnalyzeReviewResponse.model_fields) == {"success", "data", "error"}


def test_product_summary_contract_unchanged():
    assert set(AISummaryResponse.model_fields) == {
        "summary",
        "common_pros",
        "common_cons",
        "key_themes",
        "source_label",
    }
