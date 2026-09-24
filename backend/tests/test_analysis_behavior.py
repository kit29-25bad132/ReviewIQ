"""Phase 3 tests: offline end-to-end analysis behavior.

Proves that a realistic Gemini payload carries through the actual analyzer
path unchanged by architecture:

    Gemini payload -> JSON parsing -> ReviewAnalysis validation
    -> evidence grounding -> final returned ReviewAnalysis

No real Gemini API call is made: the google-genai SDK is faked with the
existing _FakeResponse / _install_fake_sdk pattern from
tests/test_model_configuration.py.

Scenarios:
 1. positive review
 2. negative review
 3. neutral review
 4. mixed review (overall + contrasting aspect sentiments)
 5. single aspect
 6. multiple aspects
 7. contrasting aspects (required ABSA behavior)
 8. pros extraction
 9. cons extraction
10. summary reflects review content
11. explicit rating
12. inferred rating
13. rating not found (null)
14. evidence-backed regression (supported survive, fabricated removed)

Grounding mechanics themselves are Phase 2 and are NOT re-tested here;
these tests only prove Phase 3 analysis behavior stays compatible with
Phase 2 grounding through the live analyzer path.
"""

import json

from models.review import AspectSentiment, PointEvidence, ReviewAnalysis
from services.ai_analyzer import analyzer_service
from services.grounding_service import is_evidence_supported
from tests.test_model_configuration import _FakeResponse, _install_fake_sdk


def run_analyzer(monkeypatch, review_text: str, payload: dict) -> ReviewAnalysis:
    """Install fake SDK with a canned payload and run the full analyzer path."""
    attempts = []
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(_FakeResponse, "text", json.dumps(payload))
    _install_fake_sdk(monkeypatch, attempts)
    result = analyzer_service._call_google_genai(review_text)
    assert isinstance(result, ReviewAnalysis)
    assert attempts, "fake SDK was not invoked"
    return result


# ---------------------------------------------------------------------------
# SCENARIO 1 — POSITIVE REVIEW
# ---------------------------------------------------------------------------

def test_positive_review_behavior(monkeypatch):
    review = (
        "The battery lasts all day and the display is bright and sharp. "
        "Setup was easy and the phone feels fast."
    )
    payload = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "A positive review praising battery life, display quality, easy setup, and smooth performance.",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day"},
            {"aspect": "display", "sentiment": "positive",
             "evidence": "the display is bright and sharp"},
            {"aspect": "setup", "sentiment": "positive",
             "evidence": "Setup was easy"},
            {"aspect": "performance", "sentiment": "positive",
             "evidence": "the phone feels fast"},
        ],
        "pros": [
            {"point": "All-day battery life", "evidence": "The battery lasts all day"},
            {"point": "Bright, sharp display", "evidence": "the display is bright and sharp"},
            {"point": "Fast performance", "evidence": "the phone feels fast"},
        ],
        "cons": [],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert result.sentiment == "positive"
    assert len(result.pros) == 3
    assert all(isinstance(p, PointEvidence) for p in result.pros)
    assert all(p.evidence for p in result.pros)
    assert len(result.aspects) == 4
    assert all(isinstance(a, AspectSentiment) for a in result.aspects)
    assert result.summary
    assert result.rating == 5
    assert result.rating_source == "inferred"
    assert result.cons == []
    # No fabricated evidence survives: every evidence string must be
    # contained (normalized) in the original review.
    for item in [*result.pros, *result.aspects]:
        assert is_evidence_supported(review, item.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 2 — NEGATIVE REVIEW
# ---------------------------------------------------------------------------

def test_negative_review_behavior(monkeypatch):
    review = (
        "The battery drains quickly and the camera produces blurry photos. "
        "The phone also gets hot during normal use."
    )
    payload = {
        "sentiment": "negative",
        "rating": 2,
        "rating_source": "inferred",
        "summary": "A negative review citing fast battery drain, blurry camera output, and overheating during normal use.",
        "aspects": [
            {"aspect": "battery", "sentiment": "negative",
             "evidence": "The battery drains quickly"},
            {"aspect": "camera", "sentiment": "negative",
             "evidence": "the camera produces blurry photos"},
            {"aspect": "temperature", "sentiment": "negative",
             "evidence": "The phone also gets hot during normal use"},
        ],
        "pros": [],
        "cons": [
            {"point": "Fast battery drain", "evidence": "The battery drains quickly"},
            {"point": "Blurry camera", "evidence": "the camera produces blurry photos"},
            {"point": "Overheating issues", "evidence": "The phone also gets hot during normal use"},
        ],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert result.sentiment == "negative"
    battery = next(a for a in result.aspects if a.aspect == "battery")
    camera = next(a for a in result.aspects if a.aspect == "camera")
    assert battery.sentiment == "negative"
    assert camera.sentiment == "negative"
    assert len(result.cons) == 3
    assert all(isinstance(c, PointEvidence) for c in result.cons)
    assert result.pros == []
    assert result.summary
    for item in [*result.cons, *result.aspects]:
        assert is_evidence_supported(review, item.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 3 — NEUTRAL REVIEW
# ---------------------------------------------------------------------------

def test_neutral_review_behavior(monkeypatch):
    review = (
        "The phone has a 6.1-inch display and comes with a USB-C cable. "
        "It weighs 170 grams."
    )
    payload = {
        "sentiment": "neutral",
        "rating": None,
        "rating_source": "not_found",
        "summary": "A factual review listing display size, included accessories, and device weight.",
        "aspects": [
            {"aspect": "display", "sentiment": "neutral",
             "evidence": "The phone has a 6.1-inch display"},
            {"aspect": "weight", "sentiment": "neutral",
             "evidence": "It weighs 170 grams"},
        ],
        "pros": [],
        "cons": [],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert result.sentiment == "neutral"
    assert result.rating is None
    assert result.rating_source == "not_found"
    assert len(result.aspects) == 2
    assert all(a.sentiment == "neutral" for a in result.aspects)
    # No fabricated positive/negative claims
    assert result.pros == []
    assert result.cons == []
    assert result.summary
    for a in result.aspects:
        assert is_evidence_supported(review, a.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 4 — MIXED REVIEW (overall + contrasting aspects)
# ---------------------------------------------------------------------------

def test_mixed_review_behavior(monkeypatch):
    review = (
        "The battery lasts all day and charges quickly, "
        "but the camera takes blurry photos at night."
    )
    payload = {
        "sentiment": "mixed",
        "rating": 3,
        "rating_source": "inferred",
        "summary": "Mixed feedback: excellent battery life and charging speed, but poor low-light camera quality.",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day and charges quickly"},
            {"aspect": "camera", "sentiment": "negative",
             "evidence": "the camera takes blurry photos at night"},
        ],
        "pros": [
            {"point": "All-day battery with fast charging",
             "evidence": "The battery lasts all day and charges quickly"},
        ],
        "cons": [
            {"point": "Blurry night photography",
             "evidence": "the camera takes blurry photos at night"},
        ],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert result.sentiment == "mixed"
    battery = next(a for a in result.aspects if a.aspect == "battery")
    camera = next(a for a in result.aspects if a.aspect == "camera")
    assert battery.sentiment == "positive"
    assert camera.sentiment == "negative"
    assert len(result.pros) == 1
    assert len(result.cons) == 1
    assert result.summary
    for item in [*result.pros, *result.cons, *result.aspects]:
        assert is_evidence_supported(review, item.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 5 — SINGLE ASPECT
# ---------------------------------------------------------------------------

def test_single_aspect_behavior(monkeypatch):
    review = "The battery easily lasts through a full day."
    payload = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "Positive review focused on all-day battery life.",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery easily lasts through a full day"},
        ],
        "pros": [
            {"point": "Excellent battery endurance",
             "evidence": "The battery easily lasts through a full day"},
        ],
        "cons": [],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert len(result.aspects) == 1
    aspect = result.aspects[0]
    assert aspect.aspect == "battery"
    assert aspect.sentiment == "positive"
    assert is_evidence_supported(review, aspect.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 6 — MULTIPLE ASPECTS
# ---------------------------------------------------------------------------

def test_multiple_aspects_behavior(monkeypatch):
    review = (
        "The battery lasts all day, the screen is bright, "
        "and the speakers sound clear."
    )
    payload = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "Positive review highlighting battery, screen brightness, and speaker clarity.",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day"},
            {"aspect": "screen", "sentiment": "positive",
             "evidence": "the screen is bright"},
            {"aspect": "speakers", "sentiment": "positive",
             "evidence": "the speakers sound clear"},
        ],
        "pros": [
            {"point": "All-day battery", "evidence": "The battery lasts all day"},
            {"point": "Bright screen", "evidence": "the screen is bright"},
            {"point": "Clear speakers", "evidence": "the speakers sound clear"},
        ],
        "cons": [],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert len(result.aspects) == 3
    aspect_names = {a.aspect for a in result.aspects}
    assert aspect_names == {"battery", "screen", "speakers"}
    assert all(a.sentiment == "positive" for a in result.aspects)
    for a in result.aspects:
        assert is_evidence_supported(review, a.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 7 — CONTRASTING ASPECTS (required ABSA behavior)
# ---------------------------------------------------------------------------

def test_contrasting_aspects_behavior(monkeypatch):
    review = "The battery lasts all day, but the camera is disappointing."
    payload = {
        "sentiment": "mixed",
        "rating": 3,
        "rating_source": "inferred",
        "summary": "Mixed review: strong battery life but disappointing camera quality.",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day"},
            {"aspect": "camera", "sentiment": "negative",
             "evidence": "the camera is disappointing"},
        ],
        "pros": [
            {"point": "Strong battery life", "evidence": "The battery lasts all day"},
        ],
        "cons": [
            {"point": "Disappointing camera", "evidence": "the camera is disappointing"},
        ],
    }
    result = run_analyzer(monkeypatch, review, payload)

    battery = next(a for a in result.aspects if a.aspect == "battery")
    camera = next(a for a in result.aspects if a.aspect == "camera")
    assert battery.sentiment == "positive"
    assert camera.sentiment == "negative"
    assert len(result.aspects) == 2
    assert len(result.pros) == 1
    assert len(result.cons) == 1
    assert is_evidence_supported(review, battery.evidence)
    assert is_evidence_supported(review, camera.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 8 — PROS EXTRACTION
# ---------------------------------------------------------------------------

def test_pros_extraction_behavior(monkeypatch):
    review = (
        "The camera takes amazing photos and the battery easily lasts all day. "
        "Setup was quick and painless."
    )
    payload = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "Positive review praising camera quality, battery life, and easy setup.",
        "aspects": [
            {"aspect": "camera", "sentiment": "positive",
             "evidence": "The camera takes amazing photos"},
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "the battery easily lasts all day"},
        ],
        "pros": [
            {"point": "Amazing camera quality", "evidence": "The camera takes amazing photos"},
            {"point": "All-day battery", "evidence": "the battery easily lasts all day"},
            {"point": "Fast setup", "evidence": "Setup was quick and painless"},
            # Fabricated: must be removed by grounding
            {"point": "Waterproof build", "evidence": "The phone is fully waterproof"},
        ],
        "cons": [],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert len(result.pros) == 3
    assert all(isinstance(p, PointEvidence) for p in result.pros)
    points = [p.point for p in result.pros]
    assert "Waterproof build" not in points
    for p in result.pros:
        assert is_evidence_supported(review, p.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 9 — CONS EXTRACTION
# ---------------------------------------------------------------------------

def test_cons_extraction_behavior(monkeypatch):
    review = (
        "The battery drains quickly and the camera produces blurry photos. "
        "The screen also scratches easily."
    )
    payload = {
        "sentiment": "negative",
        "rating": 2,
        "rating_source": "inferred",
        "summary": "Negative review citing battery drain, blurry camera, and a scratch-prone screen.",
        "aspects": [
            {"aspect": "battery", "sentiment": "negative",
             "evidence": "The battery drains quickly"},
            {"aspect": "camera", "sentiment": "negative",
             "evidence": "the camera produces blurry photos"},
            {"aspect": "screen", "sentiment": "negative",
             "evidence": "The screen also scratches easily"},
        ],
        "pros": [],
        "cons": [
            {"point": "Rapid battery drain", "evidence": "The battery drains quickly"},
            {"point": "Blurry camera output", "evidence": "the camera produces blurry photos"},
            {"point": "Scratch-prone screen", "evidence": "The screen also scratches easily"},
            # Fabricated: must be removed by grounding
            {"point": "Defective charging port", "evidence": "The charging port stopped working after a week"},
        ],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert len(result.cons) == 3
    assert all(isinstance(c, PointEvidence) for c in result.cons)
    points = [c.point for c in result.cons]
    assert "Defective charging port" not in points
    for c in result.cons:
        assert is_evidence_supported(review, c.evidence)


# ---------------------------------------------------------------------------
# SCENARIO 10 — SUMMARY
# ---------------------------------------------------------------------------

def test_summary_reflects_review_content(monkeypatch):
    review = (
        "The battery lasts all day, but the camera is weak at night. "
        "The screen is bright and easy to read."
    )
    canned_summary = (
        "The review highlights strong all-day battery life and a bright, "
        "readable screen, while criticizing weak low-light camera performance."
    )
    payload = {
        "sentiment": "mixed",
        "rating": 3,
        "rating_source": "inferred",
        "summary": canned_summary,
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day"},
            {"aspect": "camera", "sentiment": "negative",
             "evidence": "the camera is weak at night"},
            {"aspect": "screen", "sentiment": "positive",
             "evidence": "The screen is bright and easy to read"},
        ],
        "pros": [
            {"point": "All-day battery", "evidence": "The battery lasts all day"},
            {"point": "Bright readable screen", "evidence": "The screen is bright and easy to read"},
        ],
        "cons": [
            {"point": "Weak night camera", "evidence": "the camera is weak at night"},
        ],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert result.summary
    assert result.summary.strip()
    # Canned summary corresponds to the review: mentions each main point
    # present in the review text (battery, camera, screen).
    summary_lower = result.summary.lower()
    assert "battery" in summary_lower
    assert "camera" in summary_lower
    assert "screen" in summary_lower
    # Summary is returned as part of the structured analyzer response
    assert isinstance(result, ReviewAnalysis)
    # No fabricated info introduced by the payload beyond review content:
    # grounding applies to evidence-bearing fields; summary itself must be
    # the canned value (no transformation by the analyzer path).
    assert result.summary == canned_summary


# ---------------------------------------------------------------------------
# SCENARIO 11 — EXPLICIT RATING
# ---------------------------------------------------------------------------

def test_explicit_rating_behavior(monkeypatch):
    review = "I'd give this phone 5/5. The battery is excellent."
    payload = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "explicit",
        "summary": "A glowing review awarding a perfect 5/5 rating, led by excellent battery performance.",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery is excellent"},
        ],
        "pros": [
            {"point": "Excellent battery", "evidence": "The battery is excellent"},
        ],
        "cons": [],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert result.rating == 5
    assert result.rating_source == "explicit"


# ---------------------------------------------------------------------------
# SCENARIO 12 — INFERRED RATING
# ---------------------------------------------------------------------------

def test_inferred_rating_behavior(monkeypatch):
    review = (
        "The battery is excellent and the phone is incredibly fast. "
        "I have had no complaints."
    )
    payload = {
        "sentiment": "positive",
        "rating": 5,
        "rating_source": "inferred",
        "summary": "An entirely positive review praising battery life and speed with no complaints.",
        "aspects": [
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery is excellent"},
            {"aspect": "performance", "sentiment": "positive",
             "evidence": "the phone is incredibly fast"},
        ],
        "pros": [
            {"point": "Excellent battery", "evidence": "The battery is excellent"},
            {"point": "Incredibly fast", "evidence": "the phone is incredibly fast"},
        ],
        "cons": [],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert result.rating == 5
    assert result.rating_source == "inferred"
    # Review must contain no explicit numeric rating (guard against
    # accidental explicit classification in this scenario).
    assert "5/5" not in review
    assert "stars" not in review.lower()


# ---------------------------------------------------------------------------
# SCENARIO 13 — RATING NOT FOUND
# ---------------------------------------------------------------------------

def test_rating_not_found_behavior(monkeypatch):
    review = (
        "The phone arrived yesterday. "
        "I have only tested the charging cable so far."
    )
    payload = {
        "sentiment": "neutral",
        "rating": None,
        "rating_source": "not_found",
        "summary": "An early-impressions review noting only unboxing and charging cable testing so far.",
        "aspects": [
            {"aspect": "charging cable", "sentiment": "neutral",
             "evidence": "I have only tested the charging cable so far"},
        ],
        "pros": [],
        "cons": [],
    }
    result = run_analyzer(monkeypatch, review, payload)

    assert result.rating is None
    assert result.rating_source == "not_found"


# ---------------------------------------------------------------------------
# SCENARIO 14 — EVIDENCE-BACKED ANALYSIS REGRESSION (Phase 2 compatible)
# ---------------------------------------------------------------------------

def test_evidence_backed_regression(monkeypatch):
    review = "The battery lasts all day, but the camera is blurry at night."
    payload = {
        "sentiment": "mixed",
        "rating": 3,
        "rating_source": "inferred",
        "summary": "Mixed review: reliable all-day battery but blurry nighttime camera.",
        "aspects": [
            # VALID — supported by review
            {"aspect": "battery", "sentiment": "positive",
             "evidence": "The battery lasts all day"},
            {"aspect": "camera", "sentiment": "negative",
             "evidence": "the camera is blurry at night"},
            # INVALID — fabricated, must be removed
            {"aspect": "water resistance", "sentiment": "positive",
             "evidence": "The phone is waterproof"},
        ],
        "pros": [
            # VALID
            {"point": "All-day battery", "evidence": "The battery lasts all day"},
            # INVALID — fabricated, must be removed
            {"point": "Ultra-fast charging", "evidence": "The battery charges in 15 minutes"},
        ],
        "cons": [
            # VALID
            {"point": "Blurry night camera", "evidence": "the camera is blurry at night"},
            # INVALID — fabricated, must be removed
            {"point": "Overheating issues", "evidence": "The phone overheats constantly"},
        ],
    }
    result = run_analyzer(monkeypatch, review, payload)

    # Valid evidence-backed items survive
    assert [p.point for p in result.pros] == ["All-day battery"]
    assert [c.point for c in result.cons] == ["Blurry night camera"]
    assert [a.aspect for a in result.aspects] == ["battery", "camera"]
    # Fabricated items are absent
    assert all("waterproof" not in a.evidence.lower() for a in result.aspects)
    assert all("15 minutes" not in p.evidence.lower() for p in result.pros)
    assert all("overheats" not in c.evidence.lower() for c in result.cons)
    # Non-evidence fields pass through untouched
    assert result.sentiment == "mixed"
    assert result.rating == 3
    assert result.rating_source == "inferred"
    assert result.summary
