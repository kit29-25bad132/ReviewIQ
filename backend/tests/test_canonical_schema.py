import os
from pathlib import Path
import pytest
from dotenv import dotenv_values
from services.retrieval.database import PostgresDatabase

@pytest.fixture(autouse=True)
def live_db_env(monkeypatch):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    vals = dotenv_values(env_path)
    dsn = vals.get("DATABASE_URL") or vals.get("SUPABASE_DB_URL")
    if dsn:
        monkeypatch.setenv("DATABASE_URL", dsn)


def test_canonical_database_connection():
    db = PostgresDatabase()
    assert db.is_configured(), "DATABASE_URL or SUPABASE_DB_URL must be configured."
    with db.connection() as conn:
        assert conn is not None
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            res = cur.fetchone()
            assert res[0] == 1


def test_canonical_tables_exist():
    db = PostgresDatabase()
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            tables = set(r[0] for r in cur.fetchall())
            
            assert "products" in tables
            assert "reviews" in tables
            assert "review_embeddings" in tables
            assert "data_ingestion_runs" in tables
            assert "data_quality_reports" in tables
            assert "dataset_versions" in tables


def test_canonical_products_count_and_provenance():
    db = PostgresDatabase()
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.products;")
            count = cur.fetchone()[0]
            assert count == 20, f"Expected exactly 20 canonical products, got {count}"

            # Verify provenance columns
            cur.execute("""
                SELECT source_product_id, name, brand, category, source_dataset, source_reference
                FROM public.products
                ORDER BY source_product_id;
            """)
            products = cur.fetchall()
            assert len(products) == 20
            for p in products:
                s_pid, name, brand, cat, s_dataset, s_ref = p
                assert s_pid.startswith("P")
                assert len(name) > 0
                assert len(brand) > 0
                assert len(cat) > 0
                assert s_dataset == "product_reviews_dataset.csv"
                assert s_ref == f"product_reviews_dataset.csv#product_id={s_pid}"


def test_canonical_reviews_count_and_foreign_keys():
    db = PostgresDatabase()
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.reviews;")
            review_count = cur.fetchone()[0]
            assert review_count == 1500, f"Expected exactly 1500 reviews, got {review_count}"

            # Verify zero orphan reviews
            cur.execute("""
                SELECT COUNT(*)
                FROM public.reviews r
                LEFT JOIN public.products p ON r.product_id = p.id
                WHERE p.id IS NULL;
            """)
            orphans = cur.fetchone()[0]
            assert orphans == 0, f"Found {orphans} orphan reviews!"

            # Verify rating constraints
            cur.execute("SELECT MIN(rating), MAX(rating) FROM public.reviews;")
            min_r, max_r = cur.fetchone()
            assert min_r >= 1 and max_r <= 5
