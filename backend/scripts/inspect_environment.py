"""Step 0 - Read-Only Audit and Environment Inspector."""

import csv
import json
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")

def audit_dataset():
    csv_path = ROOT_DIR / "product_reviews_dataset.csv"
    if not csv_path.exists():
        csv_path = BASE_DIR / "data" / "product_reviews_dataset.csv"
    
    print(f"=== 1. SOURCE DATASET AUDIT ===")
    print(f"Path: {csv_path} (exists: {csv_path.exists()})")
    if not csv_path.exists():
        return
    
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    print(f"Total Rows: {len(rows)}")
    print(f"Columns: {fieldnames}")
    
    products = {}
    reviews_set = set()
    ratings = {}
    categories = set()
    brands = set()
    
    for r in rows:
        pid = r.get("product_id")
        pname = r.get("product_name")
        pcat = r.get("category")
        pbrand = r.get("brand")
        rid = r.get("review_id")
        rating = r.get("rating")
        
        if pid not in products:
            products[pid] = {"name": pname, "category": pcat, "brand": pbrand, "count": 0}
        products[pid]["count"] += 1
        reviews_set.add(rid)
        ratings[rating] = ratings.get(rating, 0) + 1
        categories.add(pcat)
        brands.add(pbrand)
        
    print(f"Unique Products: {len(products)}")
    print(f"Unique Reviews: {len(reviews_set)}")
    print(f"Categories ({len(categories)}): {sorted(list(categories))}")
    print(f"Brands ({len(brands)}): {sorted(list(brands))}")
    print(f"Ratings Distribution: {ratings}")
    print("\nProducts list:")
    for pid, pinfo in sorted(products.items()):
        print(f"  [{pid}] {pinfo['name']} | {pinfo['brand']} | {pinfo['category']} ({pinfo['count']} reviews)")

def audit_supabase():
    print(f"\n=== 2. SUPABASE CONNECTION AUDIT ===")
    dsn = os.getenv("DATABASE_URL")
    print(f"DATABASE_URL present: {bool(dsn)}")
    if not dsn:
        return
    
    try:
        import psycopg
        conn = psycopg.connect(dsn, connect_timeout=10)
        cur = conn.cursor()
        print("Connected to Supabase PostgreSQL successfully.")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Existing public tables: {tables}")
        for t in tables:
            cur.execute(f"SELECT count(*) FROM public.{t};")
            cnt = cur.fetchone()[0]
            print(f"  - {t}: {cnt} rows")
        conn.close()
    except Exception as e:
        print(f"Supabase connection/query failed: {e}")

if __name__ == "__main__":
    audit_dataset()
    audit_supabase()
