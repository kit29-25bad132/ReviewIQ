"""Phase 5D — grounded summary tests."""

from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values

from services.intelligence import summary as summary_module
from services.intelligence.summary import (
    MAX_SUMMARY_SENTENCES,
    SUMMARY_SYSTEM_INSTRUCTION,
    SummaryDraft,
    count_sentences,
    generate_summary,
    validate_summary,
)

#: Verbatim clause the Phase 5 requirement mandates in the system prompt.
REQUIRED_CLAUSE = (
    "Only use information present in the provided reviews. "
    "Do not infer product specifications not mentioned in reviews. "
    "If the reviews are insufficient, say so."
)

P12 = "P12"


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    dsn = dotenv_values(env_path).get("DATABASE_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def test_system_prompt_contains_the_required_grounding_clause():
    assert REQUIRED_CLAUSE in SUMMARY_SYSTEM_INSTRUCTION


def test_count_sentences():
    assert count_sentences("One. Two. Three.") == 3
    assert count_sentences("No terminator") == 1
    assert count_sentences("") == 0


def test_validate_summary_accepts_two_to_four_sentences():
    draft = SummaryDraft(
        summary="Customers like the battery. They dislike the keyboard.",
        best_for="Commuters who need long battery life.",
    )
    assert validate_summary(draft) is draft


def test_validate_summary_accepts_a_single_accurate_sentence():
    """The lower bound is not enforced: sparse-but-accurate beats padded."""
    draft = SummaryDraft(summary="Reviews on this product are sparse.", best_for="No clear fit.")
    assert validate_summary(draft).summary


def test_validate_summary_rejects_rambling_output():
    too_long = SummaryDraft(
        summary="One. Two. Three. Four. Five.",
        best_for="Anyone.",
    )
    with pytest.raises(ValueError):
        validate_summary(too_long)
    assert count_sentences(too_long.summary) == MAX_SUMMARY_SENTENCES + 1


def test_generate_summary_returns_the_model_draft():
    draft = SummaryDraft(
        summary="Customers praise the battery life. Several dislike the keyboard.",
        best_for="Buyers who need all-day battery life.",
    )
    with patch.object(summary_module, "_try_summary", return_value=draft):
        result = generate_summary(P12, aspects=[])
    assert result is not None
    assert result.best_for == "Buyers who need all-day battery life."


def test_generate_summary_retries_then_returns_none():
    with patch.object(summary_module, "_try_summary", return_value=None) as mocked:
        assert generate_summary(P12, aspects=[]) is None
    assert mocked.call_count == 2


def test_generate_summary_returns_none_for_unknown_product():
    assert generate_summary("NONEXISTENT_99999") is None


def test_generate_summary_returns_none_when_ai_not_configured(monkeypatch):
    monkeypatch.setattr(
        summary_module.analyzer_service, "is_configured", lambda: False
    )
    assert generate_summary(P12, aspects=[]) is None


def test_generate_summary_includes_real_aspects_in_the_prompt():
    from models.intelligence import AspectResult, EvidenceItem

    aspect = AspectResult(
        aspect_name="battery life",
        sentiment="positive",
        mention_count=28,
        representative_quote=EvidenceItem(review_id="R01109", excerpt="battery backup is great"),
    )
    captured = {}

    def fake_try(prompt, product_id):
        captured["prompt"] = prompt
        return SummaryDraft(summary="Grounded.", best_for="Commuters.")

    with patch.object(summary_module, "_try_summary", side_effect=fake_try):
        generate_summary(P12, aspects=[aspect])

    assert "battery life" in captured["prompt"]
    assert "28" in captured["prompt"]
