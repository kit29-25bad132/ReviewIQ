"""Gate 1 — AI error logging must never leak raw model output (ADR-012).

Fully offline: no provider calls, no database access, no network. Every test
injects a unique canary string into model output / validation errors and then
asserts that the canary never appears in captured logs (or in the HTTP
response), while the safe diagnostic fields — operation name, exception class
and the 12-hex SHA-256 digest prefix used by the RAG citation logs — are still
present. Covered paths (the three approved Gate 1 fixes):

1. ``services.ai_analyzer._parse_and_validate`` — JSON parse failure message.
2. ``routes.review`` — ``ValueError`` handler for ``POST /api/analyze-review``.
3. ``services.gemini_summary_service.summarize_product_reviews`` — terminal
   summarization failure log.
4. ``services.gemini_summary_service.generate_product_analysis`` — product
   analysis error handler (Gate 1.1: ``last_error`` can be a ValidationError
   embedding the raw model payload).
"""

import logging
import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from services.ai_analyzer import analyzer_service
from services.cache.keys import sha256_hex

client = TestClient(app, raise_server_exceptions=False)

#: Unique canary: must never be observed in any captured log line.
CANARY = "CANARY_RAW_MODEL_OUTPUT_9f3a7c"
DIGEST_RE = re.compile(r"sha256_prefix=([0-9a-f]{12})\b")


def _messages(records):
    return [record.getMessage() for record in records]


# ---------------------------------------------------------------------------
# 1. ai_analyzer._parse_and_validate — the ValueError must carry no output
# ---------------------------------------------------------------------------


def test_parse_failure_message_excludes_raw_model_output():
    raw = f'{{"summary": "{CANARY}"'  # unclosed JSON -> JSONDecodeError
    with pytest.raises(ValueError) as excinfo:
        analyzer_service._parse_and_validate(raw)

    message = str(excinfo.value)
    assert CANARY not in message
    assert "Raw output" not in message

    # Useful diagnostics are retained: stable category, JSON position, length
    # and the non-reversible digest prefix of the offending output.
    assert message.startswith("Failed to parse AI output as JSON:")
    assert "JSONDecodeError" in message
    assert "line 1" in message and "column" in message
    assert f"output_len={len(raw)}" in message
    assert f"output_sha256_prefix={sha256_hex(raw)[:12]}" in message


def test_parse_failure_message_matches_digest_convention():
    raw = f'{{"summary": "{CANARY}"'
    with pytest.raises(ValueError) as excinfo:
        analyzer_service._parse_and_validate(raw)
    match = re.search(r"output_sha256_prefix=([0-9a-f]{12})\b", str(excinfo.value))
    assert match, "expected a 12-hex digest prefix"
    assert match.group(1) == sha256_hex(raw)[:12]


# ---------------------------------------------------------------------------
# 2. routes.review — ValueError handler: no message, no traceback
# ---------------------------------------------------------------------------


def _post_review():
    return client.post("/api/analyze-review", json={"review": "The camera is great."})


def test_review_route_value_error_log_excludes_raw_output(caplog):
    failing_message = f"1 validation error for ReviewAnalysis\n  value={CANARY}"
    with patch.object(
        analyzer_service, "analyze_review", side_effect=ValueError(failing_message)
    ):
        with caplog.at_level(logging.WARNING, logger="routes.review"):
            resp = _post_review()

    # Response contract unchanged.
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Review analysis failed validation. Please try again."
    assert CANARY not in resp.text

    records = [r for r in caplog.records if r.name == "routes.review"]
    assert records, "expected a warning log for the ValueError path"
    texts = _messages(records)

    # Privacy: neither the raw message nor a traceback (which would print it).
    assert not any(CANARY in text for text in texts)
    assert not any("validation error for ReviewAnalysis" in text for text in texts)
    assert not any(record.exc_info for record in records)

    # Safe diagnostics still present: operation, category, class, digest.
    assert any("Review analysis validation error" in text for text in texts)
    assert any("category=validation" in text for text in texts)
    assert any("error_type=ValueError" in text for text in texts)
    expected_digest = sha256_hex(failing_message)[:12]
    assert any(expected_digest in text for text in texts)


def test_review_route_configuration_error_keeps_detail_and_safe_category(caplog):
    config_message = (
        "Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env"
    )
    with patch.object(
        analyzer_service, "analyze_review", side_effect=ValueError(config_message)
    ):
        with caplog.at_level(logging.WARNING, logger="routes.review"):
            resp = _post_review()

    # Existing contract: the configuration message still reaches the client.
    assert resp.status_code == 400
    assert "GEMINI_API_KEY" in resp.json()["detail"]
    assert "CANARY" not in resp.text

    texts = _messages([r for r in caplog.records if r.name == "routes.review"])
    assert any("category=configuration" in text for text in texts)
    assert any("error_type=ValueError" in text for text in texts)
    assert any(sha256_hex(config_message)[:12] in text for text in texts)


def test_review_route_value_error_log_carries_no_exception_info(caplog):
    with patch.object(
        analyzer_service,
        "analyze_review",
        side_effect=ValueError(f"parser exploded at {CANARY}"),
    ):
        with caplog.at_level(logging.DEBUG, logger="routes.review"):
            resp = _post_review()

    assert resp.status_code == 400
    records = [r for r in caplog.records if r.name == "routes.review"]
    assert records
    assert not any(record.exc_info for record in records)
    assert not any(CANARY in text for text in _messages(records))


# ---------------------------------------------------------------------------
# 3. gemini_summary_service — terminal summarization failure log
# ---------------------------------------------------------------------------


def _summarize(monkeypatch, caplog, failing_message):
    from services.gemini_summary_service import gemini_summary_service

    monkeypatch.setattr(analyzer_service, "is_configured", lambda: True)
    with patch.object(
        gemini_summary_service,
        "_generate_summary",
        side_effect=ValueError(failing_message),
    ):
        with caplog.at_level(logging.WARNING, logger="services.gemini_summary_service"):
            result = gemini_summary_service.summarize_product_reviews(
                "Kelto Gamer 16", "Laptop", ["Runs cool under load."]
            )
    return result


def test_summary_error_log_excludes_raw_model_output(monkeypatch, caplog):
    failing_message = f"1 validation error for AISummaryResponse\n  summary={CANARY}"
    result = _summarize(monkeypatch, caplog, failing_message)

    # Existing behavior preserved: a safe fallback summary is returned.
    assert result.summary
    assert CANARY not in result.summary

    records = [
        r for r in caplog.records if r.name == "services.gemini_summary_service"
    ]
    assert records, "expected a warning log for the summarization failure"
    texts = _messages(records)

    assert any("AI summarization error" in text for text in texts)
    assert not any(CANARY in text for text in texts)
    assert not any(record.exc_info for record in records)

    # Safe diagnostics: exception class + 12-hex digest prefix.
    assert any("error_type=ValueError" in text for text in texts)
    assert any(sha256_hex(failing_message)[:12] in text for text in texts)
    assert any(DIGEST_RE.search(text) for text in texts)


# ---------------------------------------------------------------------------
# 4. gemini_summary_service — product-analysis error handler (Gate 1.1)
# ---------------------------------------------------------------------------

PRODUCT_CANARY = "CANARY_PRODUCT_ANALYSIS_RAW_OUTPUT_5d1e"


def _run_failing_product_analysis(monkeypatch, caplog):
    """Exercise the real product-analysis failure path with all I/O replaced.

    A patched ``generate_with_retry`` returns a provider-shaped success
    response whose content is valid JSON of the wrong field types. The real
    parse then fails with a Pydantic ``ValidationError`` (whose string embeds
    the payload, i.e. the raw model output), the real fallback loop stores it
    as ``last_error``, and ``raise last_error`` hands it to the handler under
    test. No AI provider, no database, no network.
    """
    import json

    from services import gemini_summary_service as gs_module
    from services.ai.contracts import AIResponse, ModelRef
    from services.gemini_summary_service import gemini_summary_service

    raw_model_output = json.dumps(
        {
            "product_id": "P900",
            "product_title": "Canary Product",
            "summary": [PRODUCT_CANARY, "second field value"],
            "pros": "not-a-list",
            "cons": [],
            "insights": [],
            "evidence": [],
        }
    )

    monkeypatch.setattr(analyzer_service, "is_configured", lambda: True)
    with (
        patch.object(gemini_summary_service.product_cache, "get", return_value=None),
        patch.object(
            gs_module,
            "build_target_chain",
            return_value=[ModelRef(provider="gemini", model="gemini-test")],
        ),
        patch.object(gs_module, "select_initial_target", return_value=None),
        patch.object(
            gs_module,
            "apply_route_decision",
            lambda chain, decision: list(chain),
        ),
        patch.object(
            gs_module,
            "generate_with_retry",
            return_value=AIResponse(
                content=raw_model_output,
                provider="gemini",
                model="gemini-test",
                success=True,
                latency_ms=1.0,
                metadata={},
            ),
        ),
    ):
        with caplog.at_level(logging.DEBUG):
            try:
                gemini_summary_service.generate_product_analysis(
                    product_id="P900",
                    product_title="Canary Product",
                    category="Laptop",
                    sample_reviews=[
                        "R00001 ★★★★★ Runs cool under load."
                    ],
                )
            except Exception as exc:
                return exc
    raise AssertionError("generate_product_analysis did not raise")


def test_product_analysis_error_log_excludes_raw_model_output(monkeypatch, caplog):
    exc = _run_failing_product_analysis(monkeypatch, caplog)

    # Contract preserved: the raw payload still travels inside the exception.
    # (``str()`` may elide long inputs; ``errors()`` carries them verbatim.)
    assert isinstance(exc, ValidationError)
    assert any(PRODUCT_CANARY in str(err.get("input")) for err in exc.errors())

    # ... but it must never reach any captured log line, any logger.
    assert not any(PRODUCT_CANARY in r.getMessage() for r in caplog.records)
    # Even a truncated/elided representation of the payload must not leak.
    fragment = PRODUCT_CANARY[:20]
    assert not any(fragment in r.getMessage() for r in caplog.records)

    service_records = [
        r for r in caplog.records if r.name == "services.gemini_summary_service"
    ]
    texts = _messages(service_records)

    # Safe operation context remains observable.
    warnings = [t for t in texts if "AI product analysis error" in t]
    assert warnings, "expected the product-analysis warning log"
    assert any("product_id=P900" in t for t in warnings)
    assert any("error_type=ValidationError" in t for t in warnings)

    # No raw message, no validation payload, no traceback frame.
    assert not any(record.exc_info for record in service_records)
    assert not any("1 validation error" in t for t in texts)
    assert not any("input_value" in t for t in texts)

    # Fallback/observability flow unchanged: consolidated outcome still emitted.
    outcome_lines = [
        r.getMessage() for r in caplog.records if "ai_request_outcome" in r.getMessage()
    ]
    assert any(
        "task=product_analysis" in t and "outcome=failure" in t
        for t in outcome_lines
    )


def test_product_analysis_exception_propagation_preserved(monkeypatch, caplog):
    from services.gemini_summary_service import gemini_summary_service

    boom = ValueError(f"simulated last_error carrying {PRODUCT_CANARY}")
    monkeypatch.setattr(analyzer_service, "is_configured", lambda: True)
    with (
        patch.object(gemini_summary_service.product_cache, "get", return_value=None),
        patch.object(
            gemini_summary_service,
            "_generate_product_structured_analysis",
            side_effect=boom,
        ),
    ):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ValueError) as excinfo:
                gemini_summary_service.generate_product_analysis(
                    product_id="P901",
                    product_title="Canary Two",
                    category=None,
                    sample_reviews=["R00002 ★★★ Runs warm."],
                )

    # Identical exception object: re-raise/propagation behavior is untouched.
    assert excinfo.value is boom

    service_records = [
        r for r in caplog.records if r.name == "services.gemini_summary_service"
    ]
    texts = _messages(service_records)
    assert not any(PRODUCT_CANARY in t for t in texts)
    assert not any(record.exc_info for record in service_records)
    assert any(
        "AI product analysis error" in t
        and "product_id=P901" in t
        and "error_type=ValueError" in t
        for t in texts
    )
