# ReviewIQ — AI Evaluation

## Status

**Implemented (V2-P10):**

- Fixed offline evaluation dataset (`backend/data/evaluation_set.json`).
- Pure deterministic metric computation (`compute_metrics` in `backend/services/evaluation_service.py`).
- Offline metric-regression tests and a deterministic metric-computation baseline.
- Dataset integrity tests.
- Adversarial input regression tests.
- Explicit retry → grounding ordering regression test.
- Generated evaluation results are gitignored (`backend/evaluation_results/`).

**Deferred — no genuine gold labels exist in this repository:**

- Aspect precision/recall and aspect-sentiment accuracy.
- Evidence/grounding quality percentages.
- RAG retrieval metrics (Recall@K, MRR, relevance benchmark).
- V1 versus V2 model comparison.

Fabricating labels for these is not acceptable. Each requires a manually annotated
benchmark that has not been created.

## Fixed Evaluation Dataset

`backend/data/evaluation_set.json` — 40 committed records, derived once from the
gitignored source CSV `backend/data/amazon_review.csv`. The tests read only the
committed JSON, so they work from a fresh checkout where the source CSV is absent.

Each record contains only information supported by the source data:

| Field | Meaning |
|---|---|
| `id` | Deterministic record id (same scheme as `dataset_service`) |
| `review_text` | Original review text, whitespace-collapsed only |
| `expected_rating` | **Human star rating** copied verbatim from the source row — the ground truth for rating |
| `expected_sentiment` | **Rule-derived** from `expected_rating` via `dataset_service.sentiment_from_rating` (1–2 negative, 3 neutral, 4–5 positive) |

**Label methodology, stated explicitly:**

1. Human star ratings are ground truth for rating.
2. Sentiment labels are *derived from rating* using the existing deterministic rule.
3. **No independent human sentiment annotation currently exists.**
4. **No aspect/evidence/pros/cons/summary gold labels exist** — and none are present
   in the dataset (`test_evaluation_dataset.py` asserts their absence).
5. No retrieval relevance benchmark currently exists.

Selection is deterministic: eligible source records (40–1200 chars, deduplicated by
normalized text) are grouped by rating, sorted by id, and stride-sampled to fixed
quotas `{1: 8, 2: 6, 3: 8, 4: 9, 5: 9}`, emitted in ascending rating order.

Integrity is enforced by `backend/tests/test_evaluation_dataset.py`.

## Metrics (offline, deterministic)

`compute_metrics(rows)` is a **pure function**: no network, no provider calls, no
filesystem side effects, no cache. The live `EvaluationService` uses it internally;
the API response model (`EvaluationMetrics`) and both evaluation endpoints are
unchanged.

1. **Rating accuracy** — exact match, averaged over rated rows.
2. **Rating MAE** — mean absolute error over rated rows.
3. **Sentiment accuracy** — exact match over all rows.
4. **Confusion matrix** — 5×5, actual rating × predicted rating.

Behavior preserved from V1:

- `rating_source = "not_found"` (null predicted rating) rows are **excluded** from
  rating accuracy/MAE and the confusion matrix, but still counted in
  `evaluated_reviews` and sentiment accuracy.
- Predicted ratings outside 1–5 are never rated.
- All metrics rounded to 4 decimals.
- Methodology string unchanged.

Unit tests: `backend/tests/test_evaluation_metrics.py` (direct calls, never mocked).

## Metric-Regression Baseline (not model quality)

`backend/tests/fixtures/evaluation_baseline.json` +
`backend/tests/test_evaluation_baseline.py`.

- The predictions inside are **hand-authored fixtures** that exercise the metric
  machinery. They are **not model outputs** and require no API key, provider,
  network, or cache state.
- The test recomputes metrics with `compute_metrics()` and asserts exact equality
  with the recorded `expected_metrics`, proving deterministic recomputation.

**What this baseline proves:** *"the evaluation metric implementation remains stable."*

**What it does NOT prove:** *"Gemini achieves X% accuracy."*

Never present baseline values as model accuracy, and never report invented
percentages.

## Adversarial Input Regression (offline)

`backend/tests/test_adversarial_inputs.py`:

- Unicode/emoji review text accepted and processed deterministically.
- Prompt-like / instruction-injection text is handled strictly as review *content*
  (it never enters the system instruction).
- Extra/unknown fields are ignored by the request/response contracts (current
  Pydantic default behavior — tested and documented, not changed).
- Duplicate and conflicting review inputs stay plain deterministic inputs.
- Long-but-valid reviews (exactly 5000 chars accepted; 5001 rejected).

## Retry → Grounding Ordering

`test_retry_policy.py::test_retry_then_grounding_removes_unsupported_evidence`
pins the ordering: transient rate-limit → retry on the same target → successful
generation → parse/Pydantic validation → grounding → final grounded result.

## Live Model Evaluation (separate, opt-in)

The V1 live evaluation remains available and unchanged:

- `POST /api/evaluation/run` (Gemini required, `limit` capped) writes predictions to
  `backend/evaluation_results/results.json` — a generated, **gitignored** file.
- `GET /api/evaluation` returns the cached `EvaluationMetrics`.
- Live runs are never part of the normal pytest suite (offline suite only mocks
  these routes).

## Rules

Never report invented percentages. Clearly distinguish exact-match metrics, human
judgment, and qualitative observations. Keep the metric-regression baseline
strictly separate from model-quality evaluation.
