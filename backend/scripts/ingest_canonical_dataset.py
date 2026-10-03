"""Canonical Dataset Ingestion Pipeline for Supabase PostgreSQL.

Executes quality gate, validates pandera schema, generates foreign keys,
preserves provenance, and populates canonical products, reviews, and quality artifacts.
"""

import ast
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.retrieval.database import PostgresDatabase
from services.quality.quality_gate import quality_gate_runner


def parse_metadata_field(val: Any) -> Any:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (dict, list)):
        return val
    val_str = str(val).strip()
    if not val_str:
        return None
    try:
        return json.loads(val_str)
    except Exception:
        pass
    try:
        return ast.literal_eval(val_str)
    except Exception:
        return val_str


def ingest_canonical_dataset(csv_path: Path) -> bool:
    print(f"\n==================================================")
    print(f" REVIEWIQ CANONICAL INGESTION PIPELINE")
    print(f" Source: {csv_path}")
    print(f"==================================================")

    # 1. Execute Quality Gate
    passed, q_report = quality_gate_runner.evaluate_csv(csv_path)
    if not passed:
        print(f"\n[FATAL] Data Quality Gate FAILED with reasons:")
        for r in q_report.hard_failure_reasons:
            print(f"  - {r}")
        return False

    print(f"[OK] Quality Gate PASSED (Trustworthiness Score: {q_report.trustworthiness_score}/100)")

    # 2. Read Dataset
    df = pd.read_csv(csv_path)
    total_rows = len(df)
    dataset_name = csv_path.name
    dataset_hash = q_report.dataset_version

    db = PostgresDatabase()
    if not db.is_configured():
        print("[FATAL] Postgres database is not configured. Set DATABASE_URL.")
        return False

    with db.connection() as conn:
        with conn.cursor() as cur:
            # 3. Create Ingestion Run Record
            cur.execute("""
                INSERT INTO public.data_ingestion_runs (
                    dataset_name, dataset_version, source_path, processed_rows, 
                    validation_status, quality_status, metrics
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                dataset_name, dataset_hash, str(csv_path), total_rows,
                "PENDING", "PENDING", json.dumps({"started": datetime.utcnow().isoformat()})
            ))
            run_id = cur.fetchone()[0]

            print(f"[OK] Ingestion run registered with ID: {run_id}")

            # 4. Clean existing data in canonical tables to maintain exact 1-to-1 sync
            print("Cleaning prior canonical data...")
            cur.execute("DELETE FROM public.reviews;")
            cur.execute("DELETE FROM public.products;")

            # 5. Extract unique products from CSV
            product_group = df.groupby("product_id").first().reset_index()
            print(f"Ingesting {len(product_group)} canonical products...")

            product_id_to_uuid = {}
            for _, row in product_group.iterrows():
                pid = str(row["product_id"]).strip()
                pname = str(row["product_name"]).strip()
                brand = str(row["brand"]).strip()
                cat = str(row["category"]).strip()
                price = float(row["price_inr"]) if "price_inr" in row and not pd.isna(row["price_inr"]) else 0.0

                prod_meta = {
                    "price_inr": price,
                    "first_ingested": datetime.utcnow().isoformat(),
                }
                src_ref = f"{dataset_name}#product_id={pid}"

                cur.execute("""
                    INSERT INTO public.products (
                        source_product_id, name, brand, category, metadata, 
                        source_dataset, source_reference
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    pid, pname, brand, cat, json.dumps(prod_meta),
                    dataset_name, src_ref
                ))
                p_uuid = cur.fetchone()[0]
                product_id_to_uuid[pid] = p_uuid

            print(f"[OK] Successfully ingested {len(product_id_to_uuid)} products.")

            # 6. Ingest all reviews
            print(f"Ingesting {len(df)} canonical reviews with foreign keys and real provenance in batch...")
            review_params = []
            for _, row in df.iterrows():
                s_rid = str(row["review_id"]).strip()
                s_pid = str(row["product_id"]).strip()
                p_uuid = product_id_to_uuid.get(s_pid)
                if not p_uuid:
                    raise ValueError(f"Orphan review encountered: review {s_rid} for unknown product {s_pid}")

                rating = int(row["rating"])
                title = str(row["review_title"]).strip() if "review_title" in row and not pd.isna(row["review_title"]) else ""
                text = str(row["review_text"]).strip()
                rdate = str(row["review_date"]).strip() if "review_date" in row and not pd.isna(row["review_date"]) else None
                verified = bool(row["verified_purchase"]) if "verified_purchase" in row and not pd.isna(row["verified_purchase"]) else True

                # Parse metadata attributes
                meta_dict = {
                    "language": str(row.get("language", "en")),
                    "sentiment": str(row.get("sentiment", "neutral")).lower(),
                    "aspects_mentioned": parse_metadata_field(row.get("aspects_mentioned", [])),
                    "aspect_sentiments": parse_metadata_field(row.get("aspect_sentiments", {})),
                    "helpful_votes": int(row["helpful_votes"]) if "helpful_votes" in row and not pd.isna(row["helpful_votes"]) else 0,
                    "word_count": int(row["word_count"]) if "word_count" in row and not pd.isna(row["word_count"]) else len(text.split()),
                }
                src_ref = f"{dataset_name}#review_id={s_rid}"

                review_params.append((
                    p_uuid, s_pid, s_rid, rating,
                    title, text, rdate, verified,
                    dataset_name, src_ref, json.dumps(meta_dict)
                ))

            cur.executemany("""
                INSERT INTO public.reviews (
                    product_id, source_product_id, source_review_id, rating,
                    review_title, review_text, review_date, verified_purchase,
                    source_dataset, source_reference, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, review_params)

            print(f"[OK] Ingested {len(review_params)} reviews successfully.")

            # 7. Ingest Quality Report
            cur.execute("""
                INSERT INTO public.data_quality_reports (
                    dataset_version, ingestion_run_id, status, total_rows, total_products,
                    total_reviews, exact_duplicate_count, normalized_duplicate_count,
                    near_duplicate_count, template_repetition_count, missing_values_count,
                    invalid_ratings_count, orphan_reviews_count, provenance_coverage_pct, metrics
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                dataset_hash, run_id, q_report.status, q_report.total_rows, q_report.total_products,
                q_report.total_reviews, q_report.exact_duplicate_count, q_report.normalized_duplicate_count,
                q_report.near_duplicate_count, q_report.template_repetition_count, q_report.missing_values_count,
                q_report.invalid_ratings_count, q_report.orphan_reviews_count, q_report.provenance_coverage_pct,
                json.dumps(q_report.model_dump())
            ))

            # 8. Record Dataset Version
            file_sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            cur.execute("""
                INSERT INTO public.dataset_versions (
                    version_tag, dataset_name, row_count, product_count, sha256_hash, is_active
                ) VALUES (%s, %s, %s, %s, %s, true)
                ON CONFLICT (version_tag) DO UPDATE 
                SET is_active = true, row_count = EXCLUDED.row_count, product_count = EXCLUDED.product_count;
            """, (
                dataset_hash, dataset_name, total_rows, len(product_group), file_sha256
            ))

            # 9. Finalize Ingestion Run
            cur.execute("""
                UPDATE public.data_ingestion_runs
                SET completed_at = timezone('utc'::text, now()),
                    accepted_rows = %s,
                    rejected_rows = 0,
                    validation_status = 'VALIDATED',
                    quality_status = 'PASSED',
                    metrics = %s
                WHERE id = %s;
            """, (
                total_rows,
                json.dumps({
                    "completed": datetime.utcnow().isoformat(),
                    "trustworthiness_score": q_report.trustworthiness_score,
                    "products_ingested": len(product_group),
                    "reviews_ingested": total_rows,
                }),
                run_id
            ))

            conn.commit()
            print(f"[OK] All canonical transactions successfully committed to Supabase!")

    return True


if __name__ == "__main__":
    csv_file = ROOT_DIR / "product_reviews_dataset.csv"
    if not csv_file.exists():
        csv_file = BASE_DIR / "data" / "product_reviews_dataset.csv"

    success = ingest_canonical_dataset(csv_file)
    if not success:
        sys.exit(1)
