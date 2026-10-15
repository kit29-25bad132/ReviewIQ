"""LangGraph orchestration for Phase 5 product intelligence (5B/5C/5D).

Mirrors ``services.analysis_graph`` (START -> attempt -> route) but is typed for
an arbitrary result instead of a single-review ``ReviewAnalysis``, so the
product-level stages can share one orchestrator without changing the review
analysis contract.

Orchestration only. Prompt building, provider selection, generation, JSON
parsing, Pydantic validation, and evidence grounding stay in each stage's own
service, exactly as the review pipeline separates them.
"""

import logging
from typing import Any, Callable, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)

#: ``attempt_fn(target)`` returns a result, or raises to advance to the next
#: target. Raising is the only way to signal a failure — the graph records it
#: and moves on.
AttemptFn = Callable[[Any], Any]


class IntelligenceGraphState(TypedDict, total=False):
    """Graph state. ``targets`` are provider-qualified ``ModelRef`` objects."""

    targets: List[Any]
    current_index: int
    result: Optional[Any]
    last_error: Optional[Exception]
    attempts: int


def _make_attempt_node(attempt_fn: AttemptFn):
    def attempt(state: IntelligenceGraphState) -> dict:
        targets = state.get("targets") or []
        index = state.get("current_index", 0)
        attempts = state.get("attempts", 0) + 1
        target = targets[index]
        try:
            result = attempt_fn(target)
        except Exception as exc:  # advance to the next target
            logger.warning(
                "Intelligence attempt failed (index=%s, provider=%s, model=%s): %s",
                index,
                getattr(target, "provider", None),
                getattr(target, "model", None),
                type(exc).__name__,
            )
            return {"current_index": index + 1, "last_error": exc, "attempts": attempts}
        return {"result": result, "attempts": attempts}

    return attempt


def _route_result(state: IntelligenceGraphState) -> str:
    if state.get("result") is not None:
        return END
    if state.get("current_index", 0) < len(state.get("targets") or []):
        return "attempt"
    return END


def build_intelligence_graph(attempt_fn: AttemptFn):
    """Compile START -> attempt -> route (route loops until a result or exhaustion)."""
    builder = StateGraph(IntelligenceGraphState)
    builder.add_node("attempt", _make_attempt_node(attempt_fn))
    builder.add_edge(START, "attempt")
    builder.add_conditional_edges("attempt", _route_result, {"attempt": "attempt", END: END})
    return builder.compile()


def run_intelligence_graph(
    targets: List[Any], attempt_fn: AttemptFn
) -> IntelligenceGraphState:
    """Run the fallback graph and return the final state.

    Never raises: the caller inspects ``result`` (success) or ``last_error``
    (every target failed) and decides how to surface it.
    """
    if not targets:
        return {"targets": [], "current_index": 0, "result": None, "last_error": None, "attempts": 0}

    graph = build_intelligence_graph(attempt_fn)
    initial: IntelligenceGraphState = {
        "targets": list(targets),
        "current_index": 0,
        "result": None,
        "last_error": None,
        "attempts": 0,
    }
    return graph.invoke(initial)  # type: ignore[return-value]
