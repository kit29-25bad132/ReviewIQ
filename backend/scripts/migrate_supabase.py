"""Supabase PostgreSQL Migration Runner for ReviewIQ Canonical Data Architecture."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")

def run_migration():
    dsn = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not dsn:
        print("ERROR: DATABASE_URL or SUPABASE_DB_URL environment variable is required.")
        sys.exit(1)

    import psycopg
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg.connect(dsn)
    cur = conn.cursor()

    print("Checking existing tables in public schema...")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    existing_tables = set(r[0] for r in cur.fetchall())
    print(f"Existing tables: {existing_tables}")

    # Check if products or reviews need to be restructured to canonical schema
    if "products" in existing_tables:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'products';")
        prod_cols = set(r[0] for r in cur.fetchall())
        if "source_product_id" not in prod_cols:
            print("Migrating legacy products table to canonical products schema...")
            cur.execute("DROP TABLE IF EXISTS public.reviews CASCADE;")
            cur.execute("DROP TABLE IF EXISTS public.products CASCADE;")

    if "reviews" in existing_tables:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'reviews';")
        rev_cols = set(r[0] for r in cur.fetchall())
        if "source_review_id" not in rev_cols or "source_product_id" not in rev_cols:
            print("Migrating legacy reviews table to canonical reviews schema...")
            cur.execute("DROP TABLE IF EXISTS public.reviews CASCADE;")

    sql_path = ROOT_DIR / "supabase_canonical_schema.sql"
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    print(f"Executing migration from {sql_path.name}...")
    cur.execute(sql_content)
    conn.commit()
    print("Migration applied successfully!")

    # Verify tables
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    tables_after = [r[0] for r in cur.fetchall()]
    print(f"Verified public tables after migration: {sorted(tables_after)}")
    conn.close()

if __name__ == "__main__":
    run_migration()
