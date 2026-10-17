"""Gate 12 regression: provider-neutral OpenAPI wording.

The live, user-visible artifact here is the generated OpenAPI document
itself (`/openapi.json`, rendered at `/docs`) — not source text — so these
assertions exercise a real runtime contract: AI analysis and evaluation are
served by a configured multi-provider fallback chain (Gemini -> Groq ->
OpenRouter), so no OpenAPI summary/description may assert that a specific
provider performed or will perform a request. Provider *configuration*
references (env-var names, health `ai_provider` label) remain legitimate and
are intentionally out of scope for this file.
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# Operations whose summaries/descriptions were corrected in Gates 11-12.
OPERATIONS = (
    ("/api/analyze-review", "post"),
    ("/api/evaluation/run", "post"),
    ("/api/products/{product_id}/analysis", "get"),
    ("/api/products/{product_id}/analyze", "post"),
    ("/api/products/{product_id}/ai-summary", "post"),
)

BANNED_PROVIDER_NAMES = ("Gemini", "Groq", "OpenRouter")


def _openapi() -> dict:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    return resp.json()


def test_corrected_operations_exist():
    spec = _openapi()
    for path, method in OPERATIONS:
        assert path in spec["paths"], f"missing path {path}"
        assert method in spec["paths"][path], f"missing {method} on {path}"


def test_evaluation_run_summary_is_provider_neutral():
    spec = _openapi()
    summary = spec["paths"]["/api/evaluation/run"]["post"].get("summary", "")
    assert summary == "Explicitly run AI evaluation"
    for name in BANNED_PROVIDER_NAMES:
        assert name not in summary


def test_no_openapi_summary_or_description_names_a_provider():
    spec = _openapi()
    for path, method in OPERATIONS:
        operation = spec["paths"][path][method]
        for field in ("summary", "description"):
            text = operation.get(field) or ""
            for name in BANNED_PROVIDER_NAMES:
                assert name not in text, (
                    f"{method.upper()} {path} {field} names provider {name!r}: {text!r}"
                )


def test_evaluation_run_summary_does_not_promise_cached_results():
    # The run analyzes only records lacking a valid cached prediction, so the
    # summary must not claim the response itself is a cached artifact.
    spec = _openapi()
    summary = spec["paths"]["/api/evaluation/run"]["post"].get("summary", "")
    assert "cached" not in summary.lower()