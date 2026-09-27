"""V2-P10 tests: pure deterministic metric computation (compute_metrics).

Exercises the real V1 metric implementation directly — no mocks, no network,
no filesystem. Locks rating accuracy, rating MAE, sentiment accuracy, the 5x5
confusion matrix, and the rating_source="not_found" exclusion semantics.
"""

from services.evaluation_service import EVALUATION_METHODOLOGY, compute_metrics


def _row(
    actual,
    predicted,
    actual_sentiment="positive",
    predicted_sentiment="positive",
    source="inferred",
):
    return {
        "actual_rating": actual,
        "predicted_rating": predicted,
        "predicted_rating_source": source,
        "actual_sentiment": actual_sentiment,
        "predicted_sentiment": predicted_sentiment,
    }


# ---------------------------------------------------------------------------
# Perfect / incorrect / mixed rating predictions
# ---------------------------------------------------------------------------

def test_perfect_rating_predictions():
    rows = [_row(5, 5), _row(1, 1), _row(3, 3)]
    m = compute_metrics(rows)
    assert m.evaluated_reviews == 3
    assert m.rating_accuracy == 1.0
    assert m.rating_mae == 0.0
    assert m.sentiment_accuracy == 1.0


def test_incorrect_rating_predictions():
    rows = [_row(5, 1, source="inferred"), _row(1, 5, source="inferred")]
    m = compute_metrics(rows)
    assert m.evaluated_reviews == 2
    assert m.rating_accuracy == 0.0
    assert m.rating_mae == 4.0
    assert m.rating_mae == round(abs(5 - 1) / 2 + abs(1 - 5) / 2, 4)


def test_mixed_rating_predictions():
    rows = [_row(4, 4), _row(4, 5), _row(2, 2), _row(5, 1)]
    m = compute_metrics(rows)
    assert m.rating_accuracy == 0.5
    assert m.rating_mae == round((0 + 1 + 0 + 4) / 4, 4)


def test_rating_mae_uses_absolute_error_over_rated_rows():
    rows = [_row(3, 5), _row(5, 4)]
    m = compute_metrics(rows)
    assert m.rating_mae == round((2 + 1) / 2, 4) == 1.5


# ---------------------------------------------------------------------------
# Sentiment exact match / mismatch
# ---------------------------------------------------------------------------

def test_sentiment_exact_match():
    rows = [
        _row(4, 4, "positive", "positive"),
        _row(2, 2, "negative", "negative"),
        _row(3, 3, "neutral", "neutral"),
    ]
    assert compute_metrics(rows).sentiment_accuracy == 1.0


def test_sentiment_mismatch():
    rows = [
        _row(4, 4, "positive", "positive"),
        _row(4, 4, "positive", "negative"),
        _row(4, 4, "positive", "positive"),
        _row(4, 4, "positive", "neutral"),
    ]
    assert compute_metrics(rows).sentiment_accuracy == 0.5


def test_sentiment_accuracy_counts_rows_with_unusable_rating_prediction():
    rows = [
        _row(4, None, "positive", "positive", source="not_found"),
        _row(4, 6, "positive", "negative", source="not_found"),
    ]
    m = compute_metrics(rows)
    assert m.sentiment_accuracy == 0.5
    assert m.rating_accuracy == 0.0
    assert m.rating_mae == 0.0


# ---------------------------------------------------------------------------
# Confusion matrix dimensions / content
# ---------------------------------------------------------------------------

def test_confusion_matrix_is_5x5_of_ints():
    matrix = compute_metrics([_row(1, 1)]).confusion_matrix
    assert len(matrix) == 5
    assert all(len(row) == 5 for row in matrix)
    assert all(isinstance(cell, int) for row in matrix for cell in row)


def test_confusion_matrix_content():
    rows = [
        _row(1, 2),
        _row(3, 3),
        _row(5, 4),
        _row(5, 5),
        _row(5, 5),
    ]
    matrix = compute_metrics(rows).confusion_matrix
    assert matrix[0][1] == 1
    assert matrix[2][2] == 1
    assert matrix[4][3] == 1
    assert matrix[4][4] == 2
    assert sum(sum(row) for row in matrix) == 5
    assert matrix[1] == [0, 0, 0, 0, 0]


def test_confusion_matrix_excludes_null_predicted_rating():
    m = compute_metrics([_row(4, 4), _row(4, None, source="not_found")])
    assert sum(sum(row) for row in m.confusion_matrix) == 1
    assert m.evaluated_reviews == 2


# ---------------------------------------------------------------------------
# rating_source="not_found" exclusion semantics
# ---------------------------------------------------------------------------

def test_not_found_rows_excluded_from_rating_metrics_only():
    rows = [
        _row(5, 5, "positive", "positive", source="explicit"),
        _row(2, None, "negative", "negative", source="not_found"),
    ]
    m = compute_metrics(rows)
    assert m.evaluated_reviews == 2
    assert m.rating_accuracy == 1.0
    assert m.rating_mae == 0.0
    assert m.sentiment_accuracy == 1.0


def test_out_of_range_predicted_rating_is_not_rated():
    m = compute_metrics([_row(3, 9, "neutral", "neutral")])
    assert m.rating_accuracy == 0.0
    assert m.rating_mae == 0.0
    assert sum(sum(row) for row in m.confusion_matrix) == 0
    assert m.evaluated_reviews == 1


# ---------------------------------------------------------------------------
# Empty input and deterministic rounding
# ---------------------------------------------------------------------------

def test_empty_input_returns_zeroed_metrics():
    m = compute_metrics([])
    assert m.evaluated_reviews == 0
    assert m.rating_accuracy == 0.0
    assert m.rating_mae == 0.0
    assert m.sentiment_accuracy == 0.0
    assert m.confusion_matrix == [[0] * 5 for _ in range(5)]


def test_rounding_is_deterministic_to_four_decimals():
    rows = [_row(1, 1), _row(2, 3), _row(3, 4)]
    m = compute_metrics(rows)
    assert m.rating_accuracy == 0.3333
    assert m.rating_mae == round((0 + 1 + 1) / 3, 4) == 0.6667
    m2 = compute_metrics(
        [_row(1, 1), _row(2, 3), _row(3, 4)]
    )
    assert m.model_dump() == m2.model_dump()


def test_multiple_records_aggregate_across_classes():
    rows = [_row(r, r) for r in (1, 2, 3, 4, 5)] + [
        _row(5, 4, "positive", "positive")
    ]
    m = compute_metrics(rows)
    assert m.evaluated_reviews == 6
    assert m.rating_accuracy == round(5 / 6, 4)
    assert m.rating_mae == round(1 / 6, 4)
    assert m.sentiment_accuracy == 1.0
    assert m.confusion_matrix[4][4] == 1
    assert m.confusion_matrix[4][3] == 1


def test_methodology_text_is_unchanged():
    m = compute_metrics([_row(5, 5)])
    assert m.methodology == EVALUATION_METHODOLOGY
    assert m.methodology == (
        "Actual sentiment is derived from ratings: 1–2 negative, 3 neutral, "
        "4–5 positive. Reviews with rating_source 'not_found' (null predicted "
        "rating) are excluded from rating accuracy/MAE."
    )
