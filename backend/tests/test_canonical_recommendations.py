"""Phase 3 Task 4: canonical similar + recommendation cutover.

Live Supabase tests prove canonical data usage; isolated unit tests with a
deterministic two-alternative fixture prove preference-sensitive scoring
(ranking flips with the priority, not just the narrative).
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from services import ecommerce_db_service as sqlite_module

client = TestClient(app)
no_raise_client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def _no_sqlite_similar():
    return patch.object(
        sqlite_module.ecommerce_db_service,
        "_get_connection",
        side_effect=AssertionError("legacy SQLite fallback used on similar path"),
    )


def _no_sqlite_recommend():
    return patch.object(
        sqlite_module.ecommerce_db_service,
        "_get_connection",
        side_effect=AssertionError("legacy SQLite fallback used on recommendation path"),
    )


# ---------------- live integration ----------------

def test_similar_p12_returns_canonical_laptops_excluding_p12():
    with _no_sqlite_similar():
        resp = client.get("/api/products/P12/similar", params={"limit": 3})
    assert resp.status_code == 200
    items = resp.json()
    assert 1 <= len(items) <= 3
    ids = [p["product_id"] for p in items]
    assert "P12" not in ids
    assert len(set(ids)) == len(ids)
    for p in items:
        assert p["product_id"].startswith("P")
        assert p["category"] == "Laptop"
        assert p["review_count"] > 0
        assert p["average_rating"] > 0
    # Ratings and counts match the canonical catalog.
    from services.catalog.catalog_service import canonical_catalog
    for p in items:
        stats = canonical_catalog.get_product_statistics(p["product_id"])
        assert stats["total_reviews"] == p["review_count"]
        assert stats["average_rating"] == p["average_rating"]


def test_similar_unknown_product_returns_empty_list():
    with _no_sqlite_similar():
        resp = client.get("/api/products/NONEXISTENT_99999/similar")
    assert resp.status_code == 200
    assert resp.json() == []


def test_similar_unconfigured_returns_503():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(canonical_catalog, "is_configured", return_value=False):
        resp = no_raise_client.get("/api/products/P12/similar")
    assert resp.status_code == 503


def test_similar_database_error_is_not_masked():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(
        canonical_catalog, "get_product_by_id", side_effect=RuntimeError("supabase down")
    ), _no_sqlite_similar():
        resp = no_raise_client.get("/api/products/P12/similar")
    assert resp.status_code == 500


def test_recommendation_p12_uses_canonical_comparison_set():
    with _no_sqlite_recommend():
        resp = client.post(
            "/api/products/P12/recommendation",
            json={"persona": "Gamer", "priorities": ["Performance"]},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_product"]["product_id"] == "P12"
    assert data["selected_product"]["review_count"] == 95
    comp = data["comparison_products"]
    assert len(comp) >= 1
    by_id = {c["product_id"]: c for c in comp}
    assert list(by_id).count("P12") == 1
    assert sum(1 for c in comp if c["is_selected"]) == 1
    assert by_id["P12"]["is_selected"] is True
    assert all(not c["product_id"].startswith("B0") for c in comp)
    # Recommended product is a member of the comparison set.
    assert data["recommended_product"]["product_id"] in by_id
    assert data["user_priorities"] == ["Performance"]
    assert any(m["priority"] == "Performance" for m in data["priority_matches"])


def test_recommendation_unknown_product_returns_404():
    with _no_sqlite_recommend():
        resp = client.post("/api/products/NONEXISTENT_99999/recommendation", json={})
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_recommendation_unconfigured_returns_503():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(canonical_catalog, "is_configured", return_value=False):
        resp = no_raise_client.post("/api/products/P12/recommendation", json={})
    assert resp.status_code == 503


def test_recommendation_database_error_is_not_masked():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(
        canonical_catalog, "get_product_by_id", side_effect=RuntimeError("supabase down")
    ), _no_sqlite_recommend():
        resp = no_raise_client.post("/api/products/P12/recommendation", json={})
    assert resp.status_code == 500


# ---------------- isolated scoring behavior ----------------

def _two_alternative_state():
    """Deterministic fixture: X has the higher rating baseline, Y matches
    the 'design' priority, X matches the 'battery' priority."""
    def stats(pid, title, total, avg, pos, neu, neg):
        return {
            "product": {"id": pid, "source_product_id": pid, "product_title": title, "category": "Smartphone"},
            "total_reviews": total,
            "average_rating": avg,
            "rating_distribution": {},
            "sentiment_distribution": {"positive": pos, "neutral": neu, "negative": neg},
        }

    products = {
        "S": {"id": "S", "source_product_id": "S", "product_title": "Acme Phone Base",
              "brand": "Acme", "category": "Smartphone", "review_count": 10, "average_rating": 3.0},
        "X": {"id": "X", "source_product_id": "X", "product_title": "Acme Phone Endurance",
              "brand": "Acme", "category": "Smartphone", "review_count": 10, "average_rating": 5.0},
        "Y": {"id": "Y", "source_product_id": "Y", "product_title": "Acme Phone Stylish",
              "brand": "Acme", "category": "Smartphone", "review_count": 10, "average_rating": 4.0},
    }
    stat = {
        "S": stats("S", "Acme Phone Base", 10, 3.0, 3, 4, 3),
        "X": stats("X", "Acme Phone Endurance", 10, 5.0, 9, 1, 0),
        "Y": stats("Y", "Acme Phone Stylish", 10, 4.0, 5, 3, 2),
    }
    themes = {
        "S": ["Okay Build Quality"],
        "X": ["Amazing Battery Life"],
        "Y": ["Great Design Quality"],
    }
    return products, stat, themes


def _patched_service(products, stat, themes):
    from services import recommendation_service as rec_module

    fake_catalog = MagicMock()
    fake_catalog.is_configured.return_value = True
    fake_catalog.get_product_by_id.side_effect = lambda pid: products.get(pid)
    fake_catalog.get_product_statistics.side_effect = lambda pid: stat.get(pid)
    fake_catalog.get_products.side_effect = lambda category=None, limit=50, **k: (
        [products["X"], products["Y"]], 2
    )

    def fake_pros_cons(pid):
        ts = themes.get(pid, [])
        return SimpleNamespace(
            pros=[SimpleNamespace(theme=t, review_count=5, percentage=50.0, example_reviews=[t])
                  for t in ts],
            cons=[],
            top_pros=ts[:3],
            top_cons=[],
        )

    return patch.object(rec_module, "canonical_catalog", fake_catalog), patch.object(
        rec_module.pros_cons_service, "analyze_product_pros_cons", side_effect=fake_pros_cons
    )


def test_ranking_flips_when_priority_changes():
    from services.recommendation_service import recommendation_service
    from models.ecommerce import UserRequirementRequest

    products, stat, themes = _two_alternative_state()
    cat_patch, pc_patch = _patched_service(products, stat, themes)
    with cat_patch, pc_patch:
        rec_battery = recommendation_service.generate_recommendation(
            "S", UserRequirementRequest(priorities=["battery"])
        )
        rec_design = recommendation_service.generate_recommendation(
            "S", UserRequirementRequest(priorities=["design"])
        )
    # Same candidate set, different winner: ranking (not just narrative) moves.
    assert rec_battery.recommended_product.product_id == "X"
    assert rec_design.recommended_product.product_id == "Y"
    assert rec_battery.recommendation_headline != rec_design.recommendation_headline


def test_baseline_ranking_is_deterministic_without_preferences():
    from services.recommendation_service import recommendation_service
    from models.ecommerce import UserRequirementRequest

    products, stat, themes = _two_alternative_state()
    cat_patch, pc_patch = _patched_service(products, stat, themes)
    with cat_patch, pc_patch:
        first = recommendation_service.generate_recommendation("S", UserRequirementRequest())
        second = recommendation_service.generate_recommendation("S", UserRequirementRequest())
    assert first.recommended_product.product_id == second.recommended_product.product_id == "X"
    assert first.model_dump() == second.model_dump()


def test_budget_does_not_change_ranking():
    from services.recommendation_service import recommendation_service
    from models.ecommerce import UserRequirementRequest

    products, stat, themes = _two_alternative_state()
    cat_patch, pc_patch = _patched_service(products, stat, themes)
    with cat_patch, pc_patch:
        plain = recommendation_service.generate_recommendation(
            "S", UserRequirementRequest(priorities=["battery"])
        )
        budgeted = recommendation_service.generate_recommendation(
            "S", UserRequirementRequest(priorities=["battery"], budget="under 100")
        )
    assert budgeted.recommended_product.product_id == plain.recommended_product.product_id == "X"


def test_priority_alignment_scoring_units():
    from services.recommendation_service import (
        compute_priority_alignment,
        composite_candidate_score,
        priority_matches_theme,
    )

    assert compute_priority_alignment([], ["Anything"]) == 0.0
    assert compute_priority_alignment(["battery"], []) == 0.0
    assert compute_priority_alignment(["battery"], ["Amazing Battery Life"]) == 1.0
    assert compute_priority_alignment(["design"], ["Amazing Battery Life"]) == 0.0
    assert priority_matches_theme("Quality & Durability", "Quality & Durability")
    # Alignment only ever adds to the rating baseline, deterministically.
    assert composite_candidate_score(4.0, 50.0, 0.0) == 4.0 * 0.6 + 0.5 * 0.4
    assert composite_candidate_score(4.0, 50.0, 1.0) > composite_candidate_score(4.0, 50.0, 0.0)
