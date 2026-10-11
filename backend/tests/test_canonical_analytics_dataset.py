"""Phase 3 Task 5: canonical analytics + Dataset Explorer (live Supabase).

Verifies /api/analytics/overview, /api/analytics/products, and
/api/dataset/reviews are served from the canonical catalog, cross-checks
API results against independent database aggregates, and proves no
CSV/SQLite fallback remains on these paths.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from services.dataset_service import dataset_service

client = TestClient(app)
no_raise_client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def _no_csv():
    return patch.object(
        dataset_service,
        "records",
        side_effect=AssertionError("legacy CSV fallback used on analytics path"),
    )


def test_overview_matches_canonical_aggregates():
    from services.catalog.catalog_service import canonical_catalog

    with _no_csv():
        resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()
    expected = canonical_catalog.get_overview_analytics()
    assert body["total_reviews"] == expected["total_reviews"] == 1500
    assert body["average_rating"] == expected["average_rating"] == 3.48
    assert body["positive_reviews"] == expected["positive_reviews"]
    assert body["neutral_reviews"] == expected["neutral_reviews"]
    assert body["negative_reviews"] == expected["negative_reviews"]
    assert body["positive_reviews"] + body["neutral_reviews"] + body["negative_reviews"] == 1500
    dist = body["rating_distribution"]
    assert dist == {"1": 226, "2": 129, "3": 369, "4": 254, "5": 522}
    assert sum(dist.values()) == 1500


def test_products_aggregates_match_canonical_data():
    from services.catalog.catalog_service import canonical_catalog

    with _no_csv():
        resp = client.get("/api/analytics/products", params={"limit": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 20
    assert sum(p["review_count"] for p in body) == 1500
    counts = sorted((p["review_count"] for p in body), reverse=True)
    assert [p["review_count"] for p in body] == counts
    p12 = next(p for p in body if p["asin"] == "P12")
    assert p12["review_count"] == 95
    assert p12["product_name"] == "Kelto Gamer 16"
    stats = canonical_catalog.get_product_statistics("P12")
    assert p12["average_actual_rating"] == stats["average_rating"]
    assert p12["positive_reviews"] + p12["neutral_reviews"] + p12["negative_reviews"] == 95
    for p in body:
        assert p["helpful_votes"] >= 0
        assert p["average_ai_rating"] is None or 1 <= p["average_ai_rating"] <= 5


def test_dataset_explorer_total_and_shape():
    with patch.object(dataset_service, "query") as mock_query:
        resp = client.get("/api/dataset/reviews", params={"limit": 20, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1500
    assert len(body["items"]) == 20
    assert body["limit"] == 20 and body["offset"] == 0
    mock_query.assert_not_called()
    first = body["items"][0]
    assert first["id"].startswith("R")
    assert first["asin"].startswith("P")
    assert first["product_name"]
    assert first["review_text"]
    assert 1 <= first["actual_rating"] <= 5
    assert first["actual_sentiment"] in ("positive", "neutral", "negative")


def test_dataset_explorer_filters_and_pagination():
    with patch.object(dataset_service, "query") as mock_query:
        rated = client.get("/api/dataset/reviews", params={"rating": 5, "limit": 100}).json()
        sent = client.get("/api/dataset/reviews", params={"sentiment": "negative", "limit": 100}).json()
        prod = client.get("/api/dataset/reviews", params={"product": "P12", "limit": 100}).json()
        sea = client.get("/api/dataset/reviews", params={"search": "battery", "limit": 100}).json()
        p1 = client.get("/api/dataset/reviews", params={"limit": 100, "offset": 0}).json()
        p2 = client.get("/api/dataset/reviews", params={"limit": 100, "offset": 100}).json()
    mock_query.assert_not_called()
    assert rated["total"] == 522 and all(r["actual_rating"] == 5 for r in rated["items"])
    assert all(r["actual_sentiment"] == "negative" for r in sent["items"])
    assert prod["total"] == 95 and all(r["asin"] == "P12" for r in prod["items"])
    assert sea["total"] > 0
    for r in sea["items"]:
        blob = (r["review_text"] + " " + (r["product_name"] or "") + " " + r["asin"]).lower()
        assert "battery" in blob
    ids1 = {r["id"] for r in p1["items"]}
    ids2 = {r["id"] for r in p2["items"]}
    assert not (ids1 & ids2)


def test_dataset_explorer_empty_result():
    with patch.object(dataset_service, "query") as mock_query:
        resp = client.get("/api/dataset/reviews", params={"search": "zzz-no-such-review"})
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0
    mock_query.assert_not_called()


def test_analytics_and_dataset_unconfigured_503():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(canonical_catalog, "is_configured", return_value=False):
        assert no_raise_client.get("/api/analytics/overview").status_code == 503
        assert no_raise_client.get("/api/analytics/products").status_code == 503
        resp = no_raise_client.get("/api/dataset/reviews")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Review dataset is currently unavailable. Please try again later."


def test_analytics_and_dataset_errors_do_not_leak_or_fall_back():
    from services.catalog.catalog_service import canonical_catalog

    with patch.object(
        canonical_catalog, "get_overview_analytics", side_effect=RuntimeError("supabase boom")
    ), patch.object(dataset_service, "records") as mock_records:
        resp = no_raise_client.get("/api/analytics/overview")
    assert resp.status_code == 503
    assert "supabase boom" not in resp.text
    mock_records.assert_not_called()

    with patch.object(
        canonical_catalog, "query_dataset_reviews", side_effect=RuntimeError("supabase boom")
    ), patch.object(dataset_service, "query") as mock_query:
        resp = no_raise_client.get("/api/dataset/reviews")
    assert resp.status_code == 503
    assert "supabase boom" not in resp.text
    mock_query.assert_not_called()


def test_evaluation_contract_untouched():
    # Evaluation still reads the CSV-backed benchmark service in this slice;
    # this test locks that scope decision (see report) instead of migrating it silently.
    from pathlib import Path as _Path

    service_src = (_Path(__file__).resolve().parent.parent / "services" / "evaluation_service.py").read_text(encoding="utf-8")
    assert "dataset_service" in service_src
    resp = client.get("/api/evaluation")
    assert resp.status_code == 200
    assert resp.json() is None or isinstance(resp.json(), dict)
