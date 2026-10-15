"""Phase 5I — Phase 5 integration tests against live Supabase.

These are the eight assertions the Phase 5 requirement mandates:

1. the real analysis endpoint is called with a real product_id
2. the response validates against ``ProductAnalysisResponse``
3. ``average_rating`` matches a direct DB query
4. every evidence ``review_id`` exists in the reviews table
5. no claim has an empty evidence list
6. the AI summary is non-empty when reviews exist
7. a non-existent product_id returns 404
8. ``low_review_count`` is true for a product with fewer than 5 reviews

Low/zero review counts do not exist in the canonical catalog, so those cases
insert REAL test rows into Supabase (the requirement allows "test schema or
test data") and delete them again in ``finally``, leaving the corpus
byte-identical.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from main import app
from models.intelligence import ProductAnalysisResponse
from services.catalog.catalog_service import canonical_catalog
from services.intelligence import analyzer as analyzer_module

client = TestClient(app)
no_raise_client = TestClient(app, raise_server_exceptions=False)

ENDPOINT = "/api/products/{pid}/intelligence"
REVIEWS_ENDPOINT = "/api/products/{pid}/reviews"
P12 = "P12"
LOW_ID = "P5I_LOW"
EMPTY_ID = "P5I_EMPTY"


@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    dsn = dotenv_values(env_path).get("DATABASE_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)
    if not canonical_catalog.is_configured():
        pytest.skip("live Supabase DSN not configured")


def _one(sql: str, params: tuple = ()):
    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def _all(sql: str, params: tuple = ()):
    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


# ------------------------------------------------------- real test data


def _create_test_product(source_product_id: str, review_count: int) -> None:
    """Insert a real test product (+ reviews) and COMMIT so the API can see it."""
    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.products
                    (source_product_id, name, brand, category, source_dataset, source_reference)
                VALUES (%s, %s, 'TestBrand', 'TestCategory', 'p5i_test', 'p5i_test')
                RETURNING id;
                """,
                (source_product_id, f"P5I Test Product {source_product_id}"),
            )
            product_uuid = cur.fetchone()[0]
            for index in range(review_count):
                cur.execute(
                    """
                    INSERT INTO public.reviews
                        (product_id, source_product_id, source_review_id, rating,
                         review_text, review_date, verified_purchase,
                         source_dataset, source_reference, metadata)
                    VALUES (%s, %s, %s, %s, %s, '2025-01-01', true,
                            'p5i_test', 'p5i_test', %s::jsonb);
                    """,
                    (
                        product_uuid,
                        source_product_id,
                        f"{source_product_id}_R{index + 1}",
                        5 if index % 2 == 0 else 3,
                        f"Real test review {index + 1}: the build quality is solid and it works well.",
                        '{"sentiment": "positive"}',
                    ),
                )
        conn.commit()


def _delete_test_product(source_product_id: str) -> None:
    with canonical_catalog.db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.reviews WHERE source_product_id = %s;",
                (source_product_id,),
            )
            cur.execute(
                "DELETE FROM public.products WHERE source_product_id = %s;",
                (source_product_id,),
            )
        conn.commit()


@pytest.fixture
def low_review_product():
    _create_test_product(LOW_ID, 3)
    try:
        yield LOW_ID
    finally:
        _delete_test_product(LOW_ID)


@pytest.fixture
def zero_review_product():
    _create_test_product(EMPTY_ID, 0)
    try:
        yield EMPTY_ID
    finally:
        _delete_test_product(EMPTY_ID)


# ------------------------------------------------------------ 1, 2, 3, 4, 5


def test_endpoint_response_matches_the_contract_and_a_direct_db_query():
    """#1, #2, #3: real product_id, contract validation, average_rating from DB."""
    with patch.object(analyzer_module, "extract_aspects", return_value=[]), patch.object(
        analyzer_module, "generate_pros_cons", return_value=([], [])
    ), patch.object(analyzer_module, "generate_summary", return_value=None):
        resp = client.get(ENDPOINT.format(pid=P12))

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # #2 contract validation
    validated = ProductAnalysisResponse.model_validate(body)
    assert validated.data_source == "supabase"

    # #3 average_rating matches a direct DB query
    row = _one(
        """
        SELECT COUNT(*), ROUND(AVG(r.rating)::numeric, 1)
        FROM public.reviews r JOIN public.products p ON r.product_id = p.id
        WHERE p.source_product_id = %s;
        """,
        (P12,),
    )
    assert validated.statistics.total_reviews == int(row[0])
    assert validated.statistics.average_rating == float(row[1])
    assert sum(validated.statistics.rating_distribution.values()) == int(row[0])


def test_every_evidence_review_id_exists_and_no_claim_has_empty_evidence():
    """#4, #5: citations resolve to real rows; no claim is left unsupported."""
    with patch.object(analyzer_module, "extract_aspects", return_value=[]), patch.object(
        analyzer_module, "generate_summary", return_value=None
    ):
        # Use the real pros/cons generator but a deterministic model reply, so
        # the assertion tests OUR validation logic against REAL review rows.
        from services.intelligence.pros_cons import ClaimDraft, ClaimsDraft
        from services.intelligence import pros_cons as pros_cons_module

        real_ids = [
            r[0]
            for r in _all(
                """
                SELECT r.source_review_id FROM public.reviews r
                JOIN public.products p ON r.product_id = p.id
                WHERE p.source_product_id = %s LIMIT 3;
                """,
                (P12,),
            )
        ]
        draft = ClaimsDraft(
            pros=[ClaimDraft(claim="Solid build quality", evidence_review_ids=real_ids)],
            cons=[
                ClaimDraft(claim="Invented claim", evidence_review_ids=["NOT_A_REAL_ID"]),
                ClaimDraft(claim="No evidence at all", evidence_review_ids=[]),
            ],
        )
        with patch.object(
            pros_cons_module, "retrieve_evidence", return_value=([], "disabled")
        ), patch.object(pros_cons_module, "_attempt_claims", return_value=draft):
            resp = client.get(ENDPOINT.format(pid=P12))

    assert resp.status_code == 200, resp.text
    body = resp.json()

    db_ids = {
        r[0]
        for r in _all(
            """
            SELECT r.source_review_id FROM public.reviews r
            JOIN public.products p ON r.product_id = p.id
            WHERE p.source_product_id = %s;
            """,
            (P12,),
        )
    }

    # #5 no empty evidence anywhere
    for side in ("pros", "cons"):
        for claim in body[side]:
            assert claim["evidence"], f"{side} claim has empty evidence: {claim}"
            assert claim["support_count"] >= 1
            # #4 every citation exists in the reviews table
            for item in claim["evidence"]:
                assert item["review_id"] in db_ids

    # The untraceable claims must have been dropped.
    cons_claims = [c["claim"] for c in body["cons"]]
    assert "Invented claim" not in cons_claims
    assert "No evidence at all" not in cons_claims


# ------------------------------------------------------------------ 7, 8


def test_nonexistent_product_returns_404():
    """#7"""
    resp = client.get(ENDPOINT.format(pid="NONEXISTENT_99999"))
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_low_review_count_is_true_for_a_product_with_fewer_than_five_reviews(
    low_review_product,
):
    """#8 — real test rows in Supabase, deleted afterwards."""
    with patch.object(analyzer_module, "extract_aspects", return_value=[]), patch.object(
        analyzer_module, "generate_pros_cons", return_value=([], [])
    ), patch.object(analyzer_module, "generate_summary", return_value=None):
        resp = client.get(ENDPOINT.format(pid=low_review_product))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["low_review_count"] is True
    assert body["statistics"]["total_reviews"] == 3
    assert sum(body["statistics"].get("rating_distribution", {}).values()) == 3


def test_product_with_zero_reviews_returns_insufficient_reviews(zero_review_product):
    resp = client.get(ENDPOINT.format(pid=zero_review_product))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"] == "Insufficient reviews"
    assert body["statistics"]["total_reviews"] == 0
    assert body["aspects"] == [] and body["pros"] == [] and body["cons"] == []
    assert body["review_count_used"] == 0
    assert body["low_review_count"] is False


def test_test_data_is_cleaned_up(low_review_product):
    """The fixtures must not leave residue in the canonical corpus."""
    assert _one(
        "SELECT COUNT(*) FROM public.products WHERE source_product_id = %s;",
        (LOW_ID,),
    )[0] == 1  # present for the duration of the fixture
    _delete_test_product(LOW_ID)
    assert _one(
        "SELECT COUNT(*) FROM public.products WHERE source_product_id = %s;",
        (LOW_ID,),
    )[0] == 0


# --------------------------------------------------------- 6 (live AI)


def test_live_ai_pipeline_produces_grounded_non_empty_output():
    """#6 — the full Phase 5 pipeline with the REAL provider and REAL database.

    This is the only test that calls the AI provider; it is the executable form
    of the Phase 5 exit gate for one product.
    """
    resp = client.get(ENDPOINT.format(pid=P12))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    validated = ProductAnalysisResponse.model_validate(body)

    assert validated.statistics.total_reviews == 95
    assert validated.ai_unavailable is False, "live AI pipeline reported unavailable"
    # #6 summary is non-empty when reviews exist
    assert validated.summary.strip()
    assert validated.best_for.strip()

    db_ids = {
        r[0]
        for r in _all(
            """
            SELECT r.source_review_id FROM public.reviews r
            JOIN public.products p ON r.product_id = p.id
            WHERE p.source_product_id = %s;
            """,
            (P12,),
        )
    }
    assert validated.aspects, "live AI produced no aspects for a product with 95 reviews"
    for aspect in validated.aspects:
        assert aspect.mention_count >= 1
        assert aspect.representative_quote.review_id in db_ids
    for claim in validated.pros + validated.cons:
        assert claim.evidence
        for item in claim.evidence:
            assert item.review_id in db_ids
