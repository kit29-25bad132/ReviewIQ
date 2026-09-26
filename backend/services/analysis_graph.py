"""Phase 4: simple LangGraph orchestration for Gemini multi-model fallback.

LangGraph tracks the current model, runs one attempt, and routes:
  success -> END
  failure + models remaining -> attempt_model
  failure + exhausted -> END (caller raises last meaningful error)

V2-P3: an optional retrieval stage runs before the first attempt when a
``retrieve_fn`` is supplied (START -> retrieve_context -> attempt_model). The
retrieved context is stored in state under ``rag_context`` for observability;
attempt functions read it from the caller's closure (``attempt_fn`` keeps its
two-argument signature).

Orchestration only. Gemini generation, JSON parsing, Pydantic validation,
evidence grounding, and RAG retrieval itself stay in their own services.
"""

import logging
from typing import Any, Callable, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from models.review import ReviewAnalysis

logger = logging.getLogger(__name__)

AttemptFn = Callable[[str, str], ReviewAnalysis]
RetrieveFn = Callable[[str], Any]


class EmptyResponseError(Exception):
    """Raised when a Gemini model returns an empty/whitespace-only response.

    Treated as an attempt failure that advances the model index but does not
    replace a previously recorded provider/parse/validation error.
    """


class AnalysisGraphState(TypedDict, total=False):
    review_text: str
    models: List[str]
    current_model_index: int
    analysis: Optional[ReviewAnalysis]
    last_error: Optional[Exception]
    attempts: int
    # V2-P3: present only when a retrieval stage ran.
    rag_context: Any


def _make_retrieve_node(retrieve_fn: RetrieveFn):
    def retrieve_context(state: AnalysisGraphState) -> dict:
        review_text = state.get("review_text", "")
        try:
            context = retrieve_fn(review_text)
        except Exception as exc:
            # Best-effort stage: a retrieval failure must never block analysis.
            logger.warning(
                "RAG retrieval stage failed; continuing without context: %s", exc
            )
            return {"rag_context": None}
        return {"rag_context": context}

    return retrieve_context


def _make_attempt_node(attempt_fn: AttemptFn):
    def attempt_model(state: AnalysisGraphState) -> dict:
        index = state.get("current_model_index", 0)
        models = state.get("models") or []
        if index >= len(models):
            return {}
        model_name = models[index]
        review_text = state.get("review_text", "")
        try:
            analysis = attempt_fn(review_text, model_name)
        except EmptyResponseError:
            return {
                "current_model_index": index + 1,
                "attempts": state.get("attempts", 0) + 1,
            }
        except Exception as exc:
            logger.debug("Graph attempt failed for %s: %s", model_name, exc)
            return {
                "current_model_index": index + 1,
                "attempts": state.get("attempts", 0) + 1,
                "last_error": exc,
            }
        return {
            "analysis": analysis,
            "current_model_index": index + 1,
            "attempts": state.get("attempts", 0) + 1,
        }

    return attempt_model


def _route_result(state: AnalysisGraphState) -> str:
    if state.get("analysis") is not None:
        return END
    models = state.get("models") or []
    if state.get("current_model_index", 0) < len(models):
        return "attempt_model"
    return END


def build_analysis_graph(
    attempt_fn: AttemptFn,
    retrieve_fn: Optional[RetrieveFn] = None,
):
    """Compile the graph: START -> [retrieve_context ->] attempt_model -> route.

    The retrieval stage is included only when ``retrieve_fn`` is provided, so
    callers that do not opt in get the exact V1/P2 graph and state shape.
    """
    builder = StateGraph(AnalysisGraphState)
    builder.add_node("attempt_model", _make_attempt_node(attempt_fn))
    if retrieve_fn is not None:
        builder.add_node("retrieve_context", _make_retrieve_node(retrieve_fn))
        builder.add_edge(START, "retrieve_context")
        builder.add_edge("retrieve_context", "attempt_model")
    else:
        builder.add_edge(START, "attempt_model")
    builder.add_conditional_edges(
        "attempt_model",
        _route_result,
        {"attempt_model": "attempt_model", END: END},
    )
    return builder.compile()


def run_analysis_graph(
    review_text: str,
    models: List[str],
    attempt_fn: AttemptFn,
    retrieve_fn: Optional[RetrieveFn] = None,
) -> AnalysisGraphState:
    """Run the fallback graph and return the final state.

    Does not raise; the caller decides how to surface analysis/last_error.
    """
    graph = build_analysis_graph(attempt_fn, retrieve_fn=retrieve_fn)
    initial: AnalysisGraphState = {
        "review_text": review_text,
        "models": list(models),
        "current_model_index": 0,
        "analysis": None,
        "last_error": None,
        "attempts": 0,
    }
    if retrieve_fn is not None:
        initial["rag_context"] = None
    final_state: Any = graph.invoke(initial)
    return final_state
