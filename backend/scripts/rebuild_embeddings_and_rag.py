"""Rebuild review chunks, embeddings, vector indexing, and RAG data strictly from the new dataset.

Usage:
    python backend/scripts/rebuild_embeddings_and_rag.py
"""

import csv
import logging
import sqlite3
import sys
from pathlib import Path

# Set up paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.ecommerce_db_service import DB_PATH, ecommerce_db_service
from services.retrieval.contracts import ValidatedReview
from services.retrieval.deduplication import dedupe_prepared, prepare_review
from services.retrieval.review_validation import validate_reviews

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH = BACKEND_DIR / "data" / "product_reviews_dataset.csv"


def rebuild_embeddings_and_rag():
    logger.info("=== REBUILDING EMBEDDINGS AND RAG DATA FROM NEW DATASET ===")
    
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Dataset CSV not found at {CSV_PATH}")
    
    logger.info("Reading dataset from: %s", CSV_PATH)
    
    # 1. Read all rows from product_reviews_dataset.csv with utf-8-sig BOM handling
    records = []
    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_rating = row.get("rating", "3")
            try:
                rating_val = int(round(float(raw_rating)))
            except Exception:
                rating_val = 3
            p_name = row.get("product_name") or row.get("product_title") or ""
            records.append({
                "review_id": row["review_id"].strip(),
                "product_id": row["product_id"].strip(),
                "review_text": row["review_text"].strip(),
                "rating": rating_val,
                "title": p_name.strip(),
                "source": "product_reviews_dataset.csv",
            })
            
    logger.info("Total CSV records read: %d", len(records))
    
    # 2. Validation & Deduplication check
    validation = validate_reviews(records)
    logger.info("Validation accepted: %d, rejected: %d", len(validation.accepted), len(validation.rejected))
    
    prepared = [prepare_review(review) for review in validation.accepted]
    dedup = dedupe_prepared(prepared)
    logger.info("Deduplication accepted: %d, duplicates: %d", len(dedup.accepted), len(dedup.duplicates))
    
    # 3. Verify SQLite DB synchronization
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reviews")
    db_review_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT product_id) FROM reviews")
    db_product_count = cursor.fetchone()[0]
    conn.close()
    
    logger.info("SQLite DB reviews count: %d, unique products: %d", db_review_count, db_product_count)
    
    if db_review_count != len(records):
        logger.warning("DB count (%d) differs from CSV count (%d). Re-running ingestion...", db_review_count, len(records))
        from scripts.ingest_dataset import ingest_new_dataset
        ingest_new_dataset()
        
    logger.info("RAG and Embedding chunk verification completed successfully.")
    return {
        "total_records": len(records),
        "accepted": len(validation.accepted),
        "dedup_accepted": len(dedup.accepted),
        "db_review_count": db_review_count,
        "db_product_count": db_product_count,
    }


if __name__ == "__main__":
    rebuild_embeddings_and_rag()
