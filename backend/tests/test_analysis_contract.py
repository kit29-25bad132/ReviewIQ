"""Phase 1 tests: canonical V1 analysis output contract and rating honesty.

Covers:
- Rating acceptance (1-5) and rejection (0, 6, 7, 4.5, -1, non-integers).
- Null rating representable as rating=null + rating_source="not_found".
- rating_source enum (explicit | inferred | not_found), invalid values rejected.
- Cross-field rating/rating_source validation.
- Sentiment enum incl. mixed, with normalization.
- Structured pros/cons (PointEvidence) preserved as objects; malformed rejected.
- Structured aspects (AspectSentiment); invalid aspect sentiment rejected.
- Regression guard: the old silent clamp/round behavior (0->1, 6->5, 7->5,
  4.5->4) must never return a validated model.

Policy note: invalid numeric ratings must fail validation, never be clamped
or rounded into range. String inputs are never silently repaired into a
valid rating: they either fail type coercion or fail the 1-5 range check
(e.g. "7" may coerce to 7, which then fails le=5). Tests assert rejection,
never silent repair.

Evidence grounding (Phase 2) and ABSA generation (Phase 3) are intentionally
NOT tested here — only the data contract.
"""

import pytest
from pydantic import ValidationError

from models.review import (
    AspectSentiment,
    PointEvidence,
    ReviewAnalysis,
)


def make_payload(**overrides):
    base = {
        "sentiment": "positive",
        "rating": 4,
        "rating_source": "explicit",
        "summary": "A concise summary.",
        "aspects": [],
        "pros": [],
        "cons": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Rating acceptance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
def test_valid_ratings_accepted(rating):
    model = ReviewAnalysis.model_validate(
        make_payload(rating=rating, rating_source="inferred")
    )
    assert model.rating == rating


# ---------------------------------------------------------------------------
# Rating rejection (no silent clamp / round / repair)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rating", [0, 6, 7, -1])
def test_out_of_range_ratings_rejected(rating):
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(
            make_payload(rating=rating, rating_source="inferred")
        )


def test_fractional_rating_rejected():
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(
            make_payload(rating=4.5, rating_source="inferred")
        )


def test_string_rating_not_silently_repaired():
    # Policy: string inputs must not be silently converted into a valid
    # rating. A numeric string that maps out of range fails validation;
    # non-numeric strings fail validation. Neither is clamped or rounded.
    for bad in ["7", "0", "4.5", "abc"]:
        with pytest.raises(ValidationError):
            ReviewAnalysis.model_validate(
                make_payload(rating=bad, rating_source="inferred")
            )


# ---------------------------------------------------------------------------
# Null rating
# ---------------------------------------------------------------------------

def test_null_rating_with_not_found_accepted():
    model = ReviewAnalysis.model_validate(
        make_payload(rating=None, rating_source="not_found")
    )
    assert model.rating is None
    assert model.rating_source == "not_found"


def test_missing_rating_field_rejected():
    payload = make_payload()
    del payload["rating"]
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(payload)


# ---------------------------------------------------------------------------
# rating_source enum
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "source,rating",
    [("explicit", 4), ("inferred", 4), ("not_found", None)],
)
def test_valid_rating_source_accepted(source, rating):
    model = ReviewAnalysis.model_validate(
        make_payload(rating=rating, rating_source=source)
    )
    assert model.rating_source == source


@pytest.mark.parametrize("source", ["stated", "unknown", "EXPLICIT", ""])
def test_invalid_rating_source_rejected(source):
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(
            make_payload(rating=4, rating_source=source)
        )


# ---------------------------------------------------------------------------
# Cross-field rating validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rating,source",
    [
        (4, "explicit"),
        (4, "inferred"),
        (None, "not_found"),
    ],
)
def test_consistent_rating_combinations_accepted(rating, source):
    ReviewAnalysis.model_validate(make_payload(rating=rating, rating_source=source))


@pytest.mark.parametrize(
    "rating,source",
    [
        (None, "explicit"),
        (None, "inferred"),
        (4, "not_found"),
    ],
)
def test_inconsistent_rating_combinations_rejected(rating, source):
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(
            make_payload(rating=rating, rating_source=source)
        )


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["positive", "negative", "neutral", "mixed"])
def test_valid_sentiment_accepted(value):
    model = ReviewAnalysis.model_validate(make_payload(sentiment=value))
    assert model.sentiment == value


@pytest.mark.parametrize("raw,expected", [
    ("Positive", "positive"),
    ("  NEGATIVE  ", "negative"),
    ("Mixed", "mixed"),
    ("NEUTRAL", "neutral"),
])
def test_sentiment_normalization(raw, expected):
    model = ReviewAnalysis.model_validate(make_payload(sentiment=raw))
    assert model.sentiment == expected


def test_invalid_sentiment_rejected():
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(make_payload(sentiment="happy"))


# ---------------------------------------------------------------------------
# Pros/cons structure
# ---------------------------------------------------------------------------

def test_structured_pros_cons_preserved_as_objects():
    model = ReviewAnalysis.model_validate(
        make_payload(
            pros=[{"point": "Good battery", "evidence": "Battery lasts all day."}],
            cons=[{"point": "Expensive", "evidence": "The price is high."}],
        )
    )
    assert model.pros[0].point == "Good battery"
    assert model.pros[0].evidence == "Battery lasts all day."
    assert isinstance(model.pros[0], PointEvidence)
    assert model.cons[0].point == "Expensive"
    assert isinstance(model.cons[0], PointEvidence)


def test_malformed_pros_rejected():
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(make_payload(pros=[{"point": "missing evidence"}]))
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(make_payload(pros=[{"evidence": "missing point"}]))
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(make_payload(pros=["plain string not object"]))


def test_empty_pros_cons_defaults_allowed():
    model = ReviewAnalysis.model_validate(make_payload())
    assert model.pros == []
    assert model.cons == []


# ---------------------------------------------------------------------------
# Aspect structure
# ---------------------------------------------------------------------------

def test_structured_aspect_accepted():
    model = ReviewAnalysis.model_validate(
        make_payload(
            aspects=[{
                "aspect": "battery",
                "sentiment": "positive",
                "evidence": "Battery lasts all day.",
            }]
        )
    )
    assert model.aspects[0].aspect == "battery"
    assert model.aspects[0].sentiment == "positive"
    assert model.aspects[0].evidence == "Battery lasts all day."
    assert isinstance(model.aspects[0], AspectSentiment)


@pytest.mark.parametrize("value", ["positive", "negative", "neutral", "mixed"])
def test_aspect_sentiment_enum_accepted(value):
    ReviewAnalysis.model_validate(
        make_payload(
            aspects=[{"aspect": "screen", "sentiment": value, "evidence": "text"}]
        )
    )


def test_invalid_aspect_sentiment_rejected():
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(
            make_payload(
                aspects=[{"aspect": "screen", "sentiment": "happy", "evidence": "text"}]
            )
        )


def test_malformed_aspect_rejected():
    with pytest.raises(ValidationError):
        ReviewAnalysis.model_validate(
            make_payload(aspects=[{"aspect": "screen", "sentiment": "positive"}])
        )


# ---------------------------------------------------------------------------
# Regression: old silent clamp/round behavior must stay gone
# ---------------------------------------------------------------------------

def test_old_clamping_behavior_never_returns_valid_model():
    """If someone restores normalize_rating-style clamping, these inputs
    would validate as 1/5/5/4 respectively and this test must fail."""
    old_repairs = {
        0: 1,
        6: 5,
        7: 5,
        4.5: 4,
    }
    for invalid_input, forbidden_output in old_repairs.items():
        with pytest.raises(ValidationError):
            ReviewAnalysis.model_validate(
                make_payload(rating=invalid_input, rating_source="inferred")
            )
        # Belt-and-braces: no model may ever claim these repaired values
        # originated from the invalid input above.
        try:
            model = ReviewAnalysis.model_validate(
                make_payload(rating=invalid_input, rating_source="inferred")
            )
        except ValidationError:
            continue
        raise AssertionError(
            f"rating={invalid_input!r} was silently accepted "
            f"(would-be repaired value {forbidden_output!r})"
        )
