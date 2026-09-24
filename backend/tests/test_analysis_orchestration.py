"""Phase 4 tests: Gemini multi-model fallback + LangGraph orchestration.

Offline (fake google-genai SDK / stub attempt functions). No network.
Covers requirements A–P from the Phase 4 implementation spec.
"""

import json
import sys
from typing import List
from unittest import mock

import pytest

from models.review import ReviewAnalysis
from services.ai_analyzer import (
    DEFAULT_MODEL_NAME,
    FALLBACK_MODEL_NAMES,
    _build_model_list,
    analyzer_service,
)
from services.analysis_graph import (
    END,
    EmptyResponseError,
    build_analysis_graph,
    run_analysis_graph,
)


VALID_PAYLOAD = {
    "sentiment": "positive",
    "rating": 5,
    "rating_source": "inferred",
    "summary": "Great battery life.",
    "aspects": [
        {"aspect": "battery", "sentiment": "positive", "evidence": "The battery lasts all day"},
    ],
    "pros": [
        {"point": "All-day battery", "evidence": "The battery lasts all day"},
    ],
    "cons": [],
}

REVIEW = "The battery lasts all day."


def _payload_text(payload: dict) -> str:
    return json.dumps(payload)


class _Resp:
    def __init__(self, text: str):
        self.text = text


class _ScriptedModels:
    """Per-call script: Exception to raise, str for response text, None for empty."""

    def __init__(self, attempts: List[str], script):
        self.attempts = attempts
        self.script = list(script)

    def generate_content(self, model, contents, config):
        self.attempts.append(model)
        idx = len(self.attempts) - 1
        step = self.script[idx] if idx < len(self.script) else self.script[-1]
        if isinstance(step, BaseException):
            raise step
        if step is None:
            return _Resp("")
        return _Resp(step)


class _ScriptedClient:
    def __init__(self, attempts: List[str], script):
        self.models = _ScriptedModels(attempts, script)


def _install_scripted_sdk(monkeypatch, attempts: List[str], script):
    fake_genai = mock.MagicMock()
    fake_genai.Client = lambda api_key: _ScriptedClient(attempts, script)
    fake_types = mock.MagicMock()
    monkeypatch.setitem(sys.modules, "google", mock.MagicMock(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)


def _run(monkeypatch, script, review: str = REVIEW) -> ReviewAnalysis:
    attempts: List[str] = []
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _install_scripted_sdk(monkeypatch, attempts, script)
    result = analyzer_service._call_google_genai(review)
    # stash attempts on the result object for assertions via closure pattern
    _run.last_attempts = attempts
    return result


# ---------------------------------------------------------------------------
# A / J — Primary success short-circuits
# ---------------------------------------------------------------------------

def test_primary_success_skips_fallback(monkeypatch):
    result = _run(monkeypatch, [_payload_text(VALID_PAYLOAD)])
    assert isinstance(result, ReviewAnalysis)
    assert _run.last_attempts == ["gemini-3.8-flash"]
    assert _run.last_attempts == [DEFAULT_MODEL_NAME]


# ---------------------------------------------------------------------------
# B — Primary exception → second model succeeds
# ---------------------------------------------------------------------------

def test_primary_exception_falls_back(monkeypatch):
    result = _run(
        monkeypatch,
        [RuntimeError("primary boom"), _payload_text(VALID_PAYLOAD)],
    )
    assert isinstance(result, ReviewAnalysis)
    assert _run.last_attempts == [
        DEFAULT_MODEL_NAME,
        FALLBACK_MODEL_NAMES[0],
    ]


# ---------------------------------------------------------------------------
# C — Malformed JSON fallback
# ---------------------------------------------------------------------------

def test_malformed_json_falls_back(monkeypatch):
    result = _run(monkeypatch, ["{not valid json!!!", _payload_text(VALID_PAYLOAD)])
    assert isinstance(result, ReviewAnalysis)
    assert result.sentiment == "positive"
    assert _run.last_attempts == [
        DEFAULT_MODEL_NAME,
        FALLBACK_MODEL_NAMES[0],
    ]


# ---------------------------------------------------------------------------
# D — Schema validation fallback
# ---------------------------------------------------------------------------

def test_schema_invalid_json_falls_back(monkeypatch):
    invalid_schema = {
        "sentiment": "happy",
        "rating": 99,
        "rating_source": "not_found",
        "summary": "",
        "aspects": [],
        "pros": [],
        "cons": [],
    }
    result = _run(
        monkeypatch,
        [_payload_text(invalid_schema), _payload_text(VALID_PAYLOAD)],
    )
    assert isinstance(result, ReviewAnalysis)
    assert result.sentiment == "positive"
    assert _run.last_attempts == [
        DEFAULT_MODEL_NAME,
        FALLBACK_MODEL_NAMES[0],
    ]


# ---------------------------------------------------------------------------
# E — Third-model success
# ---------------------------------------------------------------------------

def test_third_model_success(monkeypatch):
    result = _run(
        monkeypatch,
        [
            RuntimeError("fail 1"),
            RuntimeError("fail 2"),
            _payload_text(VALID_PAYLOAD),
        ],
    )
    assert isinstance(result, ReviewAnalysis)
    assert _run.last_attempts == [
        DEFAULT_MODEL_NAME,
        FALLBACK_MODEL_NAMES[0],
        FALLBACK_MODEL_NAMES[1],
    ]


# ---------------------------------------------------------------------------
# F — All 5 models fail; no sixth attempt
# ---------------------------------------------------------------------------

def test_all_five_models_fail_no_sixth_attempt(monkeypatch):
    attempts: List[str] = []
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    _install_scripted_sdk(
        monkeypatch,
        attempts,
        [RuntimeError("model unavailable")],
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        analyzer_service._call_google_genai(REVIEW)
    assert len(attempts) == 5
    assert attempts == [DEFAULT_MODEL_NAME, *FALLBACK_MODEL_NAMES]
    assert len(attempts) <= 5


# ---------------------------------------------------------------------------
# G — Fallback response cannot bypass Pydantic validation
# ---------------------------------------------------------------------------

def test_fallback_response_passes_pydantic_validation(monkeypatch):
    invalid_then_valid = [
        _payload_text({"sentiment": "nope"}),
        _payload_text(VALID_PAYLOAD),
    ]
    result = _run(monkeypatch, invalid_then_valid)
    # Round-trip proves ReviewAnalysis.model_validate accepted the result
    revalidated = ReviewAnalysis.model_validate(result.model_dump())
    assert revalidated == result
    assert _run.last_attempts == [
        DEFAULT_MODEL_NAME,
        FALLBACK_MODEL_NAMES[0],
    ]


# ---------------------------------------------------------------------------
# H — Fallback response goes through grounding
# ---------------------------------------------------------------------------

def test_fallback_response_is_grounded(monkeypatch):
    with_fabricated = {
        **VALID_PAYLOAD,
        "pros": [
            {"point": "All-day battery", "evidence": "The battery lasts all day"},
            {"point": "Waterproof", "evidence": "The phone is fully waterproof"},
        ],
    }
    result = _run(
        monkeypatch,
        [RuntimeError("primary down"), _payload_text(with_fabricated)],
    )
    assert _run.last_attempts == [DEFAULT_MODEL_NAME, FALLBACK_MODEL_NAMES[0]]
    assert [p.point for p in result.pros] == ["All-day battery"]
    assert all("waterproof" not in p.evidence.lower() for p in result.pros)


# ---------------------------------------------------------------------------
# I — Grounding-filtered but valid → success, no extra model call
# ---------------------------------------------------------------------------

def test_grounding_filtered_valid_result_does_not_retry(monkeypatch):
    only_fabricated = {
        **VALID_PAYLOAD,
        "pros": [
            {"point": "Waterproof", "evidence": "The phone is fully waterproof"},
        ],
        "aspects": [],
    }
    result = _run(monkeypatch, [_payload_text(only_fabricated)])
    assert isinstance(result, ReviewAnalysis)
    assert result.pros == []
    assert _run.last_attempts == [DEFAULT_MODEL_NAME]
    assert len(_run.last_attempts) == 1


# ---------------------------------------------------------------------------
# K — Deterministic configured order
# ---------------------------------------------------------------------------

def test_deterministic_model_order():
    assert _build_model_list(None) == [
        "gemini-3.8-flash",
        "gemini-flash-latest",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]
    assert DEFAULT_MODEL_NAME == "gemini-3.8-flash"
    assert FALLBACK_MODEL_NAMES == [
        "gemini-flash-latest",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]


# ---------------------------------------------------------------------------
# L — Maximum bound + no duplicates
# ---------------------------------------------------------------------------

def test_model_list_bounded_and_deduplicated():
    default_list = _build_model_list(None)
    assert len(default_list) <= 5
    assert len(default_list) == len(set(default_list))

    override = _build_model_list("gemini-3.5-flash")
    assert len(override) <= 5
    assert len(override) == len(set(override))

    custom = _build_model_list("some-custom-model")
    assert len(custom) <= 5
    assert len(custom) == len(set(custom))


# ---------------------------------------------------------------------------
# M — Graph success routing: valid attempt → END
# ---------------------------------------------------------------------------

def test_graph_success_routes_to_end():
    calls = []

    def attempt_ok(review_text, model_name):
        calls.append(model_name)
        return ReviewAnalysis.model_validate(VALID_PAYLOAD)

    state = run_analysis_graph(REVIEW, ["model-a"], attempt_ok)
    assert state["analysis"] is not None
    assert calls == ["model-a"]
    assert state["attempts"] == 1


# ---------------------------------------------------------------------------
# N — Graph fallback routing: failed + remaining → next model
# ---------------------------------------------------------------------------

def test_graph_failure_routes_to_next_model():
    calls = []

    def attempt_fail_then_ok(review_text, model_name):
        calls.append(model_name)
        if model_name == "model-a":
            raise RuntimeError("boom")
        return ReviewAnalysis.model_validate(VALID_PAYLOAD)

    state = run_analysis_graph(
        REVIEW, ["model-a", "model-b"], attempt_fail_then_ok
    )
    assert calls == ["model-a", "model-b"]
    assert state["analysis"] is not None
    assert state["attempts"] == 2


# ---------------------------------------------------------------------------
# O — Graph exhaustion: failed + no remaining → end/failure
# ---------------------------------------------------------------------------

def test_graph_exhaustion_ends_without_analysis():
    calls = []

    def attempt_always_fails(review_text, model_name):
        calls.append(model_name)
        raise RuntimeError("always down")

    state = run_analysis_graph(
        REVIEW,
        ["model-a", "model-b", "model-c"],
        attempt_always_fails,
    )
    assert state["analysis"] is None
    assert state["last_error"] is not None
    assert str(state["last_error"]) == "always down"
    assert calls == ["model-a", "model-b", "model-c"]
    assert state["attempts"] == 3


def test_graph_empty_response_does_not_replace_last_error():
    def attempt_empty_then_error(review_text, model_name):
        if model_name == "model-a":
            raise EmptyResponseError("empty")
        raise RuntimeError("real failure")

    state = run_analysis_graph(
        REVIEW, ["model-a", "model-b"], attempt_empty_then_error
    )
    assert state["analysis"] is None
    assert state["last_error"] is not None
    assert str(state["last_error"]) == "real failure"


def test_graph_all_empty_yields_no_last_error():
    def attempt_empty(review_text, model_name):
        raise EmptyResponseError("empty")

    state = run_analysis_graph(REVIEW, ["model-a"], attempt_empty)
    assert state["analysis"] is None
    assert state["last_error"] is None


# ---------------------------------------------------------------------------
# P — Contract preservation
# ---------------------------------------------------------------------------

def test_contract_preserved_through_fallback(monkeypatch):
    result = _run(
        monkeypatch,
        [RuntimeError("down"), _payload_text(VALID_PAYLOAD)],
    )
    assert isinstance(result, ReviewAnalysis)
    dumped = result.model_dump()
    for field in (
        "sentiment",
        "rating",
        "rating_source",
        "summary",
        "aspects",
        "pros",
        "cons",
    ):
        assert field in dumped
    assert result.sentiment in {"positive", "negative", "neutral", "mixed"}
    assert result.rating is None or (1 <= result.rating <= 5)
    assert result.rating_source in {"explicit", "inferred", "not_found"}
    assert result.aspects[0].aspect == "battery"
    assert result.pros[0].point == "All-day battery"
    # Re-validate as Phase 1 contract would
    ReviewAnalysis.model_validate(dumped)


def test_graph_compiles():
    graph = build_analysis_graph(lambda t, m: ReviewAnalysis.model_validate(VALID_PAYLOAD))
    assert graph is not None
