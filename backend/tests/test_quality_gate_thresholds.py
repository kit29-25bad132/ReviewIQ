"""Gate 5 Phase 2 — quality-gate threshold regressions.

Offline: CSV fixtures are constructed in-memory and staged only to pytest
tmp_path (ephemeral; no repo files, no DB, no Supabase calls). Requires the
pandas/pandera/duckdb environment like test_data_quality_pipeline.py.
"""

import csv
import random
from pathlib import Path

from services.quality.quality_gate import quality_gate_runner

BACKEND_DIR = Path(__file__).resolve().parent.parent

COLUMNS = [
    "review_id", "product_id", "product_name", "brand", "category",
    "price_inr", "rating", "review_title", "review_text", "language",
    "sentiment", "verified_purchase", "helpful_votes", "review_date",
    "word_count",
]


def _row(rid, pid, rating, sentiment, text, brand="BrandA", category="Phones",
         product_name="Alpha One"):
    return [rid, pid, product_name, brand, category, 999, rating, "Title",
            text, "en", sentiment, True, 3, "2024-01-01", 7]


def _write(path, rows) -> Path:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return path


def test_empty_dataset_fails_gate(tmp_path):
    csv_path = _write(tmp_path / "empty.csv", [])
    passed, report = quality_gate_runner.evaluate_csv(csv_path)
    assert passed is False
    assert report.status == "FAIL"
    assert any("EMPTY_DATASET" in reason for reason in report.hard_failure_reasons)


def test_contradiction_rate_above_5pct_fails_gate(tmp_path):
    rows = [
        _row("R1", "P01", 5, "positive", "The battery lasts three full days on a single charge every time."),
        _row("R2", "P01", 5, "positive", "The display is bright vivid and easy to read in sunlight."),
        _row("R3", "P01", 4, "positive", "The camera takes sharp photos with accurate colors indoors."),
        _row("R4", "P01", 3, "neutral", "The phone arrived in a plain box with a short cable included."),
        _row("R5", "P01", 2, "negative", "The speaker crackles loudly during every phone call I make."),
        _row("R6", "P02", 5, "positive", "The sound quality stays clear at maximum volume outdoors."),
        _row("R7", "P02", 4, "positive", "The earbuds fit comfortably for several hours at a time."),
        _row("R8", "P02", 3, "neutral", "The charging case is white and roughly pocket sized today."),
        _row("R9", "P02", 1, "negative", "The left earbud stopped charging after two days of use."),
        # 1 of 10 rows = 10% contradiction rate (> 5% threshold).
        _row("R10", "P02", 5, "negative", "The packaging looked premium but the product failed immediately."),
    ]
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "c.csv", rows))
    assert passed is False
    assert report.status == "FAIL"
    assert report.contradictory_metadata_count == 1
    assert any("CONTRADICTION_RATE" in reason for reason in report.hard_failure_reasons)


def test_near_duplicate_rate_above_5pct_fails_gate(tmp_path):
    tail = " and I would recommend it to anyone shopping today for a reliable device"
    rows = [
        _row("R1", "P01", 5, "positive", "The camera takes sharp photos with accurate colors indoors."),
        _row("R2", "P01", 4, "positive", "The speaker sounds clear during long conference calls abroad."),
        _row("R3", "P01", 3, "neutral", "The phone arrived in a plain box with a short cable included."),
        _row("R4", "P01", 2, "negative", "The headphone jack crackles loudly on every single call made."),
        _row("R5", "P02", 5, "positive", "The sound quality stays clear at maximum volume outdoors."),
        _row("R6", "P02", 4, "positive", "The earbuds fit comfortably for several hours at a time."),
        _row("R7", "P02", 3, "neutral", "The charging case is white and roughly pocket sized today."),
        _row("R8", "P02", 1, "negative", "The left earbud stopped charging after two days of use."),
        # 1 near-duplicate pair in 10 rows = 10% (> 5% threshold). Long shared
        # body keeps similarity safely above 0.85; single-word difference keeps
        # the pair out of Level 2 normalized duplicates.
        _row("R9", "P01", 5, "positive", "The battery life is excellent and lasting for daily use" + tail + "."),
        _row("R10", "P01", 5, "positive", "The battery life is excellent and long lasting for daily use" + tail + "."),
    ]
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "n.csv", rows))
    assert passed is False
    assert report.status == "FAIL"
    assert report.near_duplicate_count >= 1
    assert any("NEAR_DUPLICATE_RATE" in reason for reason in report.hard_failure_reasons)


_BOUNDARY_FILLERS = [
    "The camera takes sharp photos with accurate colors indoors.",
    "The speaker sounds clear during long conference calls abroad.",
    "The phone arrived in a plain box with a short cable included.",
    "The headphone jack crackles loudly on every single call made.",
    "The sound quality stays clear at maximum volume outdoors.",
    "The earbuds fit comfortably for several hours at a time.",
    "The charging case is white and roughly pocket sized today.",
    "The left earbud stopped charging after two days of use.",
    "The battery lasts three full days on a single charge every time.",
    "The display is bright vivid and easy to read in sunlight.",
    "The speaker crackles loudly during every phone call I make.",
    "The packaging looked premium but the product failed immediately.",
    "The delivery truck arrived late on a rainy Tuesday morning.",
    "The warranty card was missing from the sealed retail box.",
    "The touchscreen responds slowly when my fingers feel cold.",
    "The fingerprint sensor unlocks the device within one second.",
    "The night mode captures surprisingly detailed city skylines.",
    "The FM radio reception fades badly inside concrete buildings.",
    "The alarm volume rises gradually instead of blaring at once.",
]

_BOUNDARY_TAIL = " and I would recommend it to anyone shopping today for a reliable device"
_BOUNDARY_N1 = "The battery life is excellent and lasting for daily use" + _BOUNDARY_TAIL + "."
_BOUNDARY_N2 = "The battery life is excellent and long lasting for daily use" + _BOUNDARY_TAIL + "."


def _boundary_rows(n_fillers):
    """Shared filler pool + exactly one near-duplicate pair (similarity ~0.97).

    The pool was verified pair-free on its own, and the long shared body
    keeps the pair far above 0.85 while filler↔corpus length ratios fall
    below the size-ratio prune bound — so every corpus below has exactly
    one near-duplicate pair regardless of size.
    """
    rows = []
    for i, text in enumerate(_BOUNDARY_FILLERS[:n_fillers]):
        rating, sentiment = (5, "positive") if i % 2 == 0 else (4, "positive")
        rows.append(_row(f"R{i + 1}", "P01" if i % 2 == 0 else "P02",
                         rating, sentiment, text))
    base = n_fillers
    rows.append(_row(f"R{base + 1}", "P01", 5, "positive", _BOUNDARY_N1))
    rows.append(_row(f"R{base + 2}", "P01", 5, "positive", _BOUNDARY_N2))
    return rows


def test_near_duplicate_rate_below_5pct_passes_gate(tmp_path):
    # 1 pair in 21 rows = 4.76% < 5% → PASS with zero hard failures.
    rows = _boundary_rows(19)
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "b476.csv", rows))
    assert report.near_duplicate_count == 1
    assert report.near_duplicate_pct == 4.76
    assert report.hard_failure_reasons == []
    assert passed is True
    assert report.status == "PASS"


def test_near_duplicate_rate_exactly_5pct_passes_gate(tmp_path):
    # 1 pair in 20 rows = 5.0% exactly. Policy is strict `>`: equality passes.
    rows = _boundary_rows(18)
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "b500.csv", rows))
    assert report.near_duplicate_count == 1
    assert report.near_duplicate_pct == 5.0
    assert report.hard_failure_reasons == []
    assert passed is True
    assert report.status == "PASS"


def test_near_duplicate_rate_above_5pct_fails_gate(tmp_path):
    # 1 pair in 19 rows ≈ 5.26% > 5% → FAIL on NEAR_DUPLICATE_RATE alone.
    rows = _boundary_rows(17)
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "b526.csv", rows))
    assert report.near_duplicate_count == 1
    assert report.near_duplicate_pct == 5.26
    assert passed is False
    assert report.status == "FAIL"
    assert any("NEAR_DUPLICATE_RATE" in reason for reason in report.hard_failure_reasons)
    # Near-duplicate rate is the ONLY failure: nothing else trips the gate.
    assert report.exact_duplicate_count == 0
    assert report.contradictory_metadata_count == 0


def test_any_exact_duplicate_fails_gate(tmp_path):
    rows = [
        _row("R1", "P01", 5, "positive", "The battery is simply outstanding in every way."),
        # Identical text under a distinct ID: exact duplicate (Level 2
        # normalized equality keeps it out of the near-duplicate count).
        _row("R2", "P01", 5, "positive", "The battery is simply outstanding in every way."),
        _row("R3", "P02", 4, "positive", "The earbuds fit comfortably for several hours at a time."),
    ]
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "e.csv", rows))
    assert passed is False
    assert report.status == "FAIL"
    assert report.exact_duplicate_count == 1
    assert any("EXACT_DUPLICATES" in reason for reason in report.hard_failure_reasons)


def test_live_like_corpus_passes_with_zero_hard_failures(tmp_path):
    # Mirrors verified live stats at full 1,500-row scale: 0 exact, 0 near-duplicate,
    # 9 contradictions (0.6% — counted but below the 5% FAIL threshold).
    # Deterministic vocabulary (seeded RNG, digit-free bodies so template
    # skeletons cannot collapse) keeps every pair well under 0.85 similarity.
    rng = random.Random(20260214)
    vocab = [
        "battery", "display", "camera", "charger", "speaker", "screen", "button",
        "cable", "signal", "volume", "design", "weight", "finish", "package",
        "delivery", "durability", "performance", "quality", "comfort", "sound",
        "brightness", "contrast", "resolution", "playback", "standby", "adapter",
        "microphone", "sensor", "lens", "flash", "zoom", "focus", "color",
        "texture", "grip", "hinge", "port", "slot", "stylus", "case",
        "strap", "mount", "docking", "cooling", "heating", "vibration",
        "waterproofing", "warranty", "manual", "setup", "update", "backup",
        "storage", "memory", "processor", "graphics", "keyboard", "trackpad",
        "stereo", "bass", "treble", "noise", "echo", "static", "range",
        "speed", "accuracy", "clarity", "sharpness", "smoothness", "build",
        "material", "plastic", "metal", "glass", "rubber", "fabric",
        "stitching", "zipper", "handle", "knob", "switch", "dial",
        "indicator", "alarm", "timer", "clock", "calendar", "reminder",
        "travel", "commute", "office", "kitchen", "garage", "garden",
        "morning", "evening", "weekend", "holiday", "gift", "return",
        "refund", "support", "technician", "helpline", "billing", "coupon",
        "discount", "bundle", "premium", "budget", "compact", "portable",
        "sturdy", "sleek", "modern", "classic", "vivid", "muted",
        "responsive", "laggy", "reliable", "fragile", "handy", "bulky",
    ]
    brands = ["BrandA", "BrandB", "BrandC", "BrandD", "BrandE"]
    categories = ["Phones", "Audio", "Kitchen", "Fitness", "Laptops"]
    rating_plan = [1] * 226 + [2] * 129 + [3] * 369 + [4] * 254 + [5] * 522
    assert len(rating_plan) == 1500
    sentiment_of = {1: "negative", 2: "negative", 3: "neutral", 4: "positive", 5: "positive"}

    rows = []
    for i in range(1500):
        pid = f"P{(i % 20) + 1:02d}"
        rating = rating_plan[i]
        # Nine deliberate 5-star/negative contradictions (rows 0-8): 0.6%.
        if i < 9:
            rating, sentiment = 5, "negative"
        else:
            sentiment = sentiment_of[rating]
        words = rng.sample(vocab, 40)
        text = "Customer review observation " + " ".join(words) + " end of observation."
        rows.append([
            f"R{i + 1:05d}", pid, f"Product {pid}", brands[i % 5], categories[i % 5],
            999, rating, "Title", text, "en", sentiment, True, i % 7,
            f"2024-{(i % 12) + 1:02d}-15", len(text.split()),
        ])

    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "live.csv", rows))
    assert passed is True
    assert report.status == "PASS"
    assert report.hard_failure_reasons == []
    assert report.total_reviews == 1500
    assert report.exact_duplicate_count == 0
    assert report.near_duplicate_count == 0
    assert report.contradictory_metadata_count == 9


# ---------------------------------------------------------------------------
# At-exactly-5% boundary pins (strict `>` semantics on both rates).
#
# A literal 5.001% is not representable with small integer fixtures:
# contradiction_pct is count/total*100 (unrounded) while near_duplicate_pct
# is rounded to 2 decimals before the same strict `>` comparison, so the
# closest pins above the boundary with small corpora are used instead.
# ---------------------------------------------------------------------------

_EXTRA_FILLERS = [
    "The remote control pairs instantly with the television set.",
    "The stand wobbles slightly on uneven wooden surfaces.",
    "The appetizer arrived cold despite the short waiting time.",
    "The hiking boots needed two full days to break in.",
    "The novel kept me awake until three in the morning.",
    "The blender crushes frozen fruit without any struggle.",
    "The office chair supports my lower back all day.",
    "The headphones survived a drop onto concrete stairs.",
    "The tomato soup tasted overly salty for my liking.",
    "The tent poles snapped during a windy mountain night.",
    "The puzzle pieces fit together with satisfying clicks.",
    "The garden hose leaks near the brass connector joint.",
    "The clock chimes softly every hour on the hour.",
    "The jacket pockets are deep enough for winter gloves.",
    "The muffins stayed moist even on the second day.",
    "The umbrella flips inside out in strong gusts.",
    "The scissors cut thick cardboard with little effort.",
    "The pillow stays cool through hot summer nights.",
    "The kettle whistles loudly once the water boils.",
    "The socks slipped down inside my running shoes.",
]

_CONTRADICTION_C1 = ("The shipping box felt luxurious but the gadget died "
                     "within minutes of unboxing.")
_CONTRADICTION_C2 = ("Five stars solely for same-day delivery since the actual "
                     "product never functioned.")

_BOUNDARY_TAIL_2 = (" and the companion mobile application syncs flawlessly "
                    "across all my personal gadgets")
_BOUNDARY_N3 = ("The display brightness adapts smoothly to evening ambient light"
                + _BOUNDARY_TAIL_2 + ".")
_BOUNDARY_N4 = ("The display brightness adapts gently to evening ambient light"
                + _BOUNDARY_TAIL_2 + ".")


def _clean_filler_rows(n):
    """First n filler sentences with contradiction-free 5/4-star ratings.

    Draws from the verified pair-free pool plus the extra pool; contains no
    near-duplicate pairs and no rating/sentiment contradictions on its own.
    """
    pool = _BOUNDARY_FILLERS + _EXTRA_FILLERS
    rows = []
    for i, text in enumerate(pool[:n]):
        rating, sentiment = (5, "positive") if i % 2 == 0 else (4, "positive")
        rows.append(_row(f"R{i + 1}", "P01" if i % 2 == 0 else "P02",
                         rating, sentiment, text))
    return rows


def test_contradiction_rate_exactly_5pct_passes_gate(tmp_path):
    # 1 contradiction in 20 rows = 5.0% exactly. Policy is strict `>`
    # (not `>=`): equality passes with zero hard failures.
    rows = _clean_filler_rows(19)
    rows.append(_row("R20", "P02", 5, "negative", _CONTRADICTION_C1))
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "c500.csv", rows))
    assert report.contradictory_metadata_count == 1
    assert report.exact_duplicate_count == 0
    assert report.near_duplicate_count == 0
    assert report.hard_failure_reasons == []
    assert passed is True
    assert report.status == "PASS"


def test_contradiction_rate_just_above_5pct_fails_gate(tmp_path):
    # 2 contradictions in 39 rows = 5.128% > 5% → FAIL on
    # CONTRADICTION_RATE alone (closest small-fixture pin above 5%).
    rows = _clean_filler_rows(37)
    rows.append(_row("R38", "P01", 5, "negative", _CONTRADICTION_C1))
    rows.append(_row("R39", "P02", 5, "negative", _CONTRADICTION_C2))
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "c513.csv", rows))
    assert report.contradictory_metadata_count == 2
    assert passed is False
    assert report.status == "FAIL"
    assert any("CONTRADICTION_RATE" in reason for reason in report.hard_failure_reasons)
    # Contradiction rate is the ONLY failure: nothing else trips the gate.
    assert report.exact_duplicate_count == 0
    assert report.near_duplicate_count == 0
    assert report.orphan_reviews_count == 0


def test_near_duplicate_rate_just_above_5pct_fails_gate(tmp_path):
    # 2 pairs in 39 rows = 5.128% > 5% → FAIL (closest small-fixture pin
    # above 5%; a literal 5.001% is unrepresentable since the rate is
    # rounded to 2 decimals before the strict `>` comparison).
    rows = _clean_filler_rows(35)
    rows.append(_row("R36", "P01", 5, "positive", _BOUNDARY_N1))
    rows.append(_row("R37", "P01", 5, "positive", _BOUNDARY_N2))
    rows.append(_row("R38", "P02", 5, "positive", _BOUNDARY_N3))
    rows.append(_row("R39", "P02", 5, "positive", _BOUNDARY_N4))
    passed, report = quality_gate_runner.evaluate_csv(_write(tmp_path / "n513.csv", rows))
    assert report.near_duplicate_count == 2
    assert report.near_duplicate_pct == 5.13
    assert passed is False
    assert report.status == "FAIL"
    assert any("NEAR_DUPLICATE_RATE" in reason for reason in report.hard_failure_reasons)
    # Near-duplicate rate is the ONLY failure: nothing else trips the gate.
    assert report.exact_duplicate_count == 0
    assert report.contradictory_metadata_count == 0
    assert report.orphan_reviews_count == 0
