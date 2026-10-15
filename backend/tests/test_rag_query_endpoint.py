"""Phase 7F hermetic tests for the rag-query route."""

import hashlib
import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services.rag.similar_reviews import RetrievalOutcome, RetrievedReview
from services.rag.answer_service import RAGAnswer, build_answer_prompt
from routes import rag_query as rq
from tests.test_ai_foundation import FakeProvider
from tests.test_observability_events import OUTCOME_FIELDS, _gateway, _outcome_events

client = TestClient(app)


def _review(review_id, text, similarity=0.7, rating=4):
    return RetrievedReview(
        review_id=review_id,
        review_text=text,
        similarity_score=similarity,
        product_id="P12",
        rating=rating,
        source_review_id=review_id,
        source="canonical",
    )


def _fake_catalog(found=True):
    return patch.object(
        rq.canonical_catalog,
        "get_product_by_id",
        return_value={"product_id": "P12"} if found else None,
    )


def test_unknown_product_returns_404():
    with _fake_catalog(found=False):
        resp = client.post(
            "/api/products/NOPE999/rag-query", json={"query": "battery?"}
        )
    assert resp.status_code == 404


def test_top_k_above_20_rejected():
    resp = client.post(
        "/api/products/P12/rag-query", json={"query": "battery?", "top_k": 21}
    )
    assert resp.status_code == 422


def test_disabled_flag_returns_empty_rag_disabled_shape():
    with _fake_catalog(), patch.object(rq, "intelligence_rag_enabled", return_value=False):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "answer": "",
        "evidence": [],
        "retrieval_count": 0,
        "context_token_estimate": 0,
        "model_used": "",
        "rag_enabled": False,
        "fallback_used": False,
    }


def test_empty_retrieval_returns_empty_answer_not_hallucinated():
    outcome = RetrievalOutcome(reviews=(), fallback_triggered=False)
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome),
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})
    body = resp.json()
    assert body["answer"] == ""
    assert body["evidence"] == []
    assert body["retrieval_count"] == 0
    assert body["rag_enabled"] is True
    assert body["fallback_used"] is False


def test_retrieval_failure_returns_empty_shape_not_500(caplog):
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(
            rq,
            "retrieve_similar_reviews_detailed",
            side_effect=RuntimeError("database unavailable"),
        ),
        caplog.at_level("ERROR", logger="routes.rag_query"),
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "answer": "",
        "evidence": [],
        "retrieval_count": 0,
        "context_token_estimate": 0,
        "model_used": "",
        "rag_enabled": True,
        "fallback_used": False,
    }
    assert any(
        "RAG retrieval failed for product P12" in rec.message for rec in caplog.records
    )


def test_success_path_evidence_excerpts_are_verbatim_substrings():
    reviews = (
        _review("R00669", "using it daily for a week. the battery life is okay, nothing special."),
        _review("R00702", "the battery life turned out superb. one charge gets me through two days.", 0.71),
    )
    outcome = RetrievalOutcome(reviews=reviews, fallback_triggered=True)
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome),
        patch.object(
            rq,
            "generate_rag_answer",
            return_value=RAGAnswer(answer="Battery life is mixed [R00669].", model_used="gemini-2.5-flash"),
        ),
    ):
        resp = client.post(
            "/api/products/P12/rag-query", json={"query": "how is the battery life?", "top_k": 10}
        )
    body = resp.json()
    assert body["answer"] == "Battery life is mixed [R00669]."
    assert body["model_used"] == "gemini-2.5-flash"
    assert body["rag_enabled"] is True
    assert body["fallback_used"] is True
    assert body["retrieval_count"] == 2
    assert body["context_token_estimate"] > 0
    # Evidence order follows reviews_used: similarity desc (0.71 then 0.70).
    assert [e["review_id"] for e in body["evidence"]] == ["R00702", "R00669"]
    full_texts = {r.review_id: r.review_text for r in reviews}
    for item in body["evidence"]:
        assert item["excerpt"] in full_texts[item["review_id"]]


def test_excerpt_cuts_at_word_boundary():
    long_text = "word " * 100 + "end."
    excerpt = rq._verbatim_excerpt(long_text, max_chars=50)
    assert len(excerpt) <= 50
    assert long_text.startswith(excerpt) or excerpt in long_text
    assert not excerpt.endswith("wor")  # never a partial final token


def test_uncited_answer_guard_coerces_empty_and_logs(caplog):
    # Gate 2 follow-up: DEBUG on root so the INFO ai_request_outcome event is
    # emitted and captured alongside the guard's WARNING record.
    caplog.set_level(logging.DEBUG)
    raw_answer = "Battery is fine."
    reviews = (_review("R00669", "the battery life is okay"),)
    outcome = RetrievalOutcome(reviews=reviews, fallback_triggered=False)
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome),
        patch.object(
            rq,
            "generate_rag_answer",
            return_value=RAGAnswer(answer=raw_answer, model_used="m"),
        ),
        patch.object(rq, "_verbatim_excerpt", return_value=""),
        # DEBUG (not WARNING): a WARNING-level at_level would lower the caplog
        # handler during the request and drop the INFO outcome event.
        caplog.at_level(logging.DEBUG, logger="routes.rag_query"),
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})
    body = resp.json()
    # Existing HTTP contract unchanged.
    assert resp.status_code == 200
    assert body["answer"] == ""
    assert body["evidence"] == []
    messages = [rec.message for rec in caplog.records]
    assert any("uncited-answer guard" in message for message in messages)
    # Safe metadata is logged: length + SHA-256 prefix (12 hex chars).
    digest = hashlib.sha256(raw_answer.encode("utf-8")).hexdigest()[:12]
    assert any(
        f"length={len(raw_answer)}" in message and digest in message
        for message in messages
    )
    # The raw LLM output must never appear in the logs (privacy).
    assert not any(raw_answer in message for message in messages)

    # Gate 2 follow-up: empty evidence discards the answer, so the route's one
    # terminal event must be a failure — never success — on the OUTCOME_FIELDS
    # contract, with rag_status=None preserved (retrieval ran upstream in the
    # route; never guessed).
    events = _outcome_events(caplog)
    assert len(events) == 1  # exactly one terminal event for the request
    (event,) = events
    assert set(event) == OUTCOME_FIELDS
    assert event["task"] == "rag_query_answer"
    assert event["outcome"] == "failure"  # discarded answer: NEVER success
    assert event["cache"] == "disabled"
    assert event["rag_status"] == "None"  # established rationale, unchanged
    assert int(event["total_ms"]) >= 0
    # The discarded answer must never leak into event metadata either.
    assert not any(raw_answer in value for value in event.values())


def test_unknown_citation_coerces_answer_and_logs(caplog):
    raw_answer = "Battery is fine [R99999]."
    reviews = (_review("R00669", "the battery life is okay"),)
    outcome = RetrievalOutcome(reviews=reviews, fallback_triggered=False)
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome),
        patch.object(
            rq,
            "generate_rag_answer",
            return_value=RAGAnswer(answer=raw_answer, model_used="m"),
        ),
        caplog.at_level("WARNING", logger="routes.rag_query"),
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})
    body = resp.json()
    assert body["answer"] == ""
    # Evidence is real and retained; only the untrustworthy answer is discarded.
    assert [e["review_id"] for e in body["evidence"]] == ["R00669"]
    messages = [rec.message for rec in caplog.records]
    assert any("R99999" in message for message in messages)  # unknown citation IDs
    # Safe metadata is logged: length + SHA-256 prefix (12 hex chars).
    digest = hashlib.sha256(raw_answer.encode("utf-8")).hexdigest()[:12]
    assert any(
        f"length={len(raw_answer)}" in message and digest in message
        for message in messages
    )
    # The raw LLM output must never appear in the logs (privacy).
    assert not any(raw_answer in message for message in messages)


def test_valid_citations_preserved():
    reviews = (_review("R00669", "the battery life is okay"),)
    outcome = RetrievalOutcome(reviews=reviews, fallback_triggered=False)
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome),
        patch.object(
            rq,
            "generate_rag_answer",
            return_value=RAGAnswer(answer="Battery is fine [R00669].", model_used="m"),
        ),
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})
    body = resp.json()
    assert body["answer"] == "Battery is fine [R00669]."
    assert [e["review_id"] for e in body["evidence"]] == ["R00669"]


def test_answer_service_prompt_contains_question_and_evidence():
    prompt = build_answer_prompt("how is the battery?", "[R00669] (rating=4) great battery")
    assert prompt == (
        "Question: how is the battery?\n\nReview evidence:\n"
        "[R00669] (rating=4) great battery"
    )


def test_system_instruction_matches_spec_verbatim():
    from services.rag.answer_service import RAG_ANSWER_SYSTEM_INSTRUCTION

    assert RAG_ANSWER_SYSTEM_INSTRUCTION == (
        "Answer using only the review evidence provided. "
        "Cite each claim with [review_id]. "
        "If the evidence does not support a claim, omit it."
    )


# ---------------------------------------------------------------------------
# Gate 1 — whitespace-only query rejected during request validation (422)
# ---------------------------------------------------------------------------


def _spies():
    """(catalog, retrieval) mock factories — an invalid request reaches neither."""
    return (
        patch.object(rq.canonical_catalog, "get_product_by_id"),
        patch.object(rq, "retrieve_similar_reviews_detailed"),
    )


def test_whitespace_only_query_rejected_422_before_retrieval():
    catalog, retrieval = _spies()
    with catalog as catalog_mock, retrieval as retrieval_mock:
        resp = client.post("/api/products/P12/rag-query", json={"query": "   \t  \n "})
    assert resp.status_code == 422
    catalog_mock.assert_not_called()
    retrieval_mock.assert_not_called()


def test_blank_and_out_of_range_requests_return_422_without_side_effects():
    for payload in (
        {"query": ""},
        {"query": " "},
        {"query": "   \t  \n "},
        {"query": "x" * 2001},                # over max_length
        {"query": "battery?", "top_k": 0},     # under ge=1
        {"query": "battery?", "top_k": 21},    # over le=20
        {"query": "battery?", "top_k": -1},
    ):
        catalog, retrieval = _spies()
        with catalog as catalog_mock, retrieval as retrieval_mock:
            resp = client.post("/api/products/P12/rag-query", json=payload)
        assert resp.status_code == 422, payload
        catalog_mock.assert_not_called()
        retrieval_mock.assert_not_called()


def test_non_empty_query_still_accepted_and_not_rewritten():
    from models.rag_query import RAGQueryRequest

    query = "  how is the battery life?  "
    request = RAGQueryRequest(query=query)
    # Contract check: only blank input is rejected; a non-empty query is kept
    # byte-for-byte (no silent trim/normalize) and top_k default is unchanged.
    assert request.query == query
    assert request.top_k == 10

    outcome = RetrievalOutcome(reviews=(), fallback_triggered=False)
    with (
        patch.object(rq.canonical_catalog, "get_product_by_id", return_value={"product_id": "P12"}),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome) as retrieval,
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": query})
    assert resp.status_code == 200
    assert retrieval.call_args.args[0] == query  # passed through verbatim


def test_length_and_top_k_bounds_unchanged():
    import pydantic

    from models.rag_query import RAGQueryRequest

    assert len(RAGQueryRequest(query="a" * 2000).query) == 2000
    with pytest.raises(pydantic.ValidationError):
        RAGQueryRequest(query="a" * 2001)
    with pytest.raises(pydantic.ValidationError):
        RAGQueryRequest(query="ok", top_k=0)
    with pytest.raises(pydantic.ValidationError):
        RAGQueryRequest(query="ok", top_k=21)
    assert RAGQueryRequest(query="ok", top_k=1).top_k == 1
    assert RAGQueryRequest(query="ok", top_k=20).top_k == 20


# ---------------------------------------------------------------------------
# Gate 2 — RAG outcome contract (exactly one accurate terminal event)
# ---------------------------------------------------------------------------

RETRIEVAL_CANARY = "CANARY_RETRIEVAL_EXCEPTION_4e2b"
ANSWER_CANARY = "CANARY_DISCARDED_ANSWER_9c1f"


def _everything(caplog) -> str:
    return "\n".join(record.getMessage() for record in caplog.records)


def test_retrieval_failure_emits_single_failure_outcome_event(caplog):
    caplog.set_level(logging.DEBUG)
    failure = RuntimeError(f"vector store unreachable {RETRIEVAL_CANARY}")
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", side_effect=failure),
        patch.object(rq, "generate_rag_answer") as answer_mock,
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})

    # Existing HTTP contract unchanged (degrades to the empty shape, never 500).
    assert resp.status_code == 200
    assert resp.json() == {
        "answer": "",
        "evidence": [],
        "retrieval_count": 0,
        "context_token_estimate": 0,
        "model_used": "",
        "rag_enabled": True,
        "fallback_used": False,
    }
    answer_mock.assert_not_called()

    events = _outcome_events(caplog)
    assert len(events) == 1  # exactly one terminal event for the request
    (event,) = events
    assert set(event) == OUTCOME_FIELDS
    assert event["task"] == "rag_query_answer"
    assert event["outcome"] == "failure"  # never success
    assert event["provider"] == "None"  # no AI target ran — never guessed
    assert event["model"] == "None"
    assert event["fallback"] == "None"
    assert event["retry_attempts"] == "None"
    assert event["retry_count"] == "None"
    assert event["provider_latency_ms"] == "None"
    assert event["cache"] == "disabled"
    assert event["rag_status"] == "None"  # established rationale, unchanged
    assert int(event["total_ms"]) >= 0
    assert event["request_id"]

    # Canary + raw exception text must never appear in logs or event fields.
    everything = _everything(caplog)
    assert RETRIEVAL_CANARY not in everything
    assert "vector store unreachable" not in everything
    assert not any(record.exc_info for record in caplog.records)  # no traceback
    for value in event.values():
        assert RETRIEVAL_CANARY not in value


def test_citation_discard_emits_single_failure_outcome_event(caplog):
    caplog.set_level(logging.DEBUG)
    raw_answer = f"{ANSWER_CANARY} Battery is fine [R99999]."
    reviews = (_review("R00669", "the battery life is okay"),)
    outcome = RetrievalOutcome(reviews=reviews, fallback_triggered=False)
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome),
        patch.object(
            rq,
            "generate_rag_answer",
            return_value=RAGAnswer(
                answer=raw_answer, model_used="m", provider="gemini"
            ),
        ),
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})

    # Existing discard behavior and response shape unchanged.
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == ""
    assert [e["review_id"] for e in body["evidence"]] == ["R00669"]
    assert body["model_used"] == "m"
    assert body["rag_enabled"] is True
    assert body["fallback_used"] is False

    events = _outcome_events(caplog)
    assert len(events) == 1  # exactly one terminal event for the request
    (event,) = events
    assert set(event) == OUTCOME_FIELDS
    assert event["task"] == "rag_query_answer"
    assert event["outcome"] == "failure"  # discarded answer: NEVER success
    assert event["provider"] == "gemini"
    assert event["model"] == "m"
    assert event["cache"] == "disabled"
    assert event["rag_status"] == "None"
    assert int(event["total_ms"]) >= 0

    # The citation-validation guard still fired (behavior not weakened).
    assert "RAG citation validation" in _everything(caplog)

    # Generated content must never leak into logs or event metadata.
    everything = _everything(caplog)
    assert ANSWER_CANARY not in everything
    assert raw_answer not in everything
    for value in event.values():
        assert ANSWER_CANARY not in value


def test_success_path_emits_exactly_one_event_with_real_service(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    provider = FakeProvider(["Battery lasts two days. [R00669]."], name="gemini")
    monkeypatch.setattr(
        "services.rag.answer_service.analyzer_service._gateway",
        _gateway({"gemini": provider}),
    )
    reviews = (_review("R00669", "the battery life is okay"),)
    outcome = RetrievalOutcome(reviews=reviews, fallback_triggered=False)
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome),
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})

    assert resp.status_code == 200
    assert resp.json()["answer"] == "Battery lasts two days. [R00669]."

    events = _outcome_events(caplog)
    # Exactly once: the service deferred its success emission and only the
    # route emits the terminal event — no duplicate from both layers.
    assert len(events) == 1
    (event,) = events
    assert set(event) == OUTCOME_FIELDS
    assert event["task"] == "rag_query_answer"
    assert event["outcome"] == "success"
    assert event["provider"] == "gemini"
    assert event["model"]
    assert event["rag_status"] == "None"
    assert int(event["total_ms"]) >= 0

    # Gate 3: no answer text or raw query payload in any log line or event
    # metadata (ADR-012: event fields are fixed safe metadata only).
    answer_text = resp.json()["answer"]
    assert answer_text not in _everything(caplog)
    assert not any(answer_text in value for value in event.values())
    assert not any("battery?" in value for value in event.values())


def test_answer_generation_failure_route_does_not_double_emit(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    provider = FakeProvider([RuntimeError("rag provider down")], name="gemini")
    monkeypatch.setattr(
        "services.rag.answer_service.analyzer_service._gateway",
        _gateway({"gemini": provider}),
    )
    reviews = (_review("R00669", "the battery life is okay"),)
    outcome = RetrievalOutcome(reviews=reviews, fallback_triggered=False)
    with (
        _fake_catalog(),
        patch.object(rq, "intelligence_rag_enabled", return_value=True),
        patch.object(rq, "retrieve_similar_reviews_detailed", return_value=outcome),
    ):
        resp = client.post("/api/products/P12/rag-query", json={"query": "battery?"})

    # Existing generation-failure response behavior unchanged.
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == ""
    assert body["evidence"] == []
    assert body["retrieval_count"] == 1
    assert body["model_used"] == ""
    assert body["rag_enabled"] is True

    events = _outcome_events(caplog)
    # The service emitted its failure event in ``finally``; the route must not
    # add a second one on this branch.
    assert len(events) == 1
    (event,) = events
    assert set(event) == OUTCOME_FIELDS
    assert event["task"] == "rag_query_answer"
    assert event["outcome"] == "failure"
    assert event["provider"] == "gemini"  # per-target metadata preserved
    assert event["cache"] == "disabled"
    assert event["rag_status"] == "None"

    # Gate 3: raw provider exception text must never enter event metadata
    # (ADR-012) — the approved WARNING logs may carry the attempt error, but
    # the event carries only fixed safe fields.
    assert not any("rag provider down" in value for value in event.values())
