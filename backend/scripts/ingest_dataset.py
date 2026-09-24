import csv
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "ecommerce_product_reviews_dataset.csv"
DB_PATH = DATA_DIR / "ecommerce_reviews.db"


def build_database():
    if not CSV_PATH.exists():
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    print(f"Starting ultra-fast ingestion of 4,000,000 rows from {CSV_PATH}...")
    start_time = time.time()

    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except Exception:
            pass

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ultra-fast SQLite pragmas
    cursor.execute("PRAGMA synchronous = 0;")
    cursor.execute("PRAGMA journal_mode = OFF;")
    cursor.execute("PRAGMA locking_mode = EXCLUSIVE;")
    cursor.execute("PRAGMA cache_size = 500000;")
    cursor.execute("PRAGMA temp_store = MEMORY;")

    cursor.execute("""
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            product_title TEXT NOT NULL,
            category TEXT,
            review_text TEXT NOT NULL,
            rating INTEGER NOT NULL,
            sentiment TEXT NOT NULL
        );
    """)

    batch_size = 100000
    batch = []
    total_rows = 0

    cursor.execute("BEGIN TRANSACTION;")

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        for row in reader:
            if len(row) < 6:
                continue

            p_id = row[0].strip()
            p_title = row[1].strip()
            cat = row[2].strip()
            rev = row[3].strip()
            try:
                rating = int(float(row[4]))
            except Exception:
                rating = 0
            sent = row[5].strip()

            if not p_id or not p_title:
                continue

            batch.append((p_id, p_title, cat, rev, rating, sent))
            total_rows += 1

            if len(batch) >= batch_size:
                cursor.executemany(
                    "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
                    batch,
                )
                print(f"[{time.time()-start_time:.1f}s] Ingested {total_rows:,} / ~4,000,000 rows...")
                batch = []

        if batch:
            cursor.executemany(
                "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
                batch,
            )

    conn.commit()
    print(f"Reviews table complete ({total_rows:,} rows in {time.time()-start_time:.1f}s). Building product aggregates...")

    # Build products pre-aggregated table
    cursor.execute("""
        CREATE TABLE products AS
        SELECT
            product_id,
            product_title,
            LOWER(TRIM(product_title)) AS normalized_title,
            category,
            COUNT(*) AS review_count,
            ROUND(AVG(rating), 2) AS average_rating,
            SUM(CASE WHEN LOWER(sentiment) = 'positive' THEN 1 ELSE 0 END) AS positive_count,
            SUM(CASE WHEN LOWER(sentiment) = 'neutral' THEN 1 ELSE 0 END) AS neutral_count,
            SUM(CASE WHEN LOWER(sentiment) = 'negative' THEN 1 ELSE 0 END) AS negative_count,
            SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS star_5_count,
            SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS star_4_count,
            SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS star_3_count,
            SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS star_2_count,
            SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS star_1_count
        FROM reviews
        GROUP BY product_id, product_title, category;
    """)

    print(f"[{time.time()-start_time:.1f}s] Creating indexes for sub-millisecond search & pagination...")
    cursor.execute("CREATE INDEX idx_products_pid ON products(product_id);")
    cursor.execute("CREATE INDEX idx_products_norm_title ON products(normalized_title);")
    cursor.execute("CREATE INDEX idx_products_title ON products(product_title);")
    cursor.execute("CREATE INDEX idx_reviews_product_id ON reviews(product_id);")
    cursor.execute("CREATE INDEX idx_reviews_pid_rating ON reviews(product_id, rating);")
    cursor.execute("CREATE INDEX idx_reviews_pid_sentiment ON reviews(product_id, sentiment);")

    conn.commit()
    conn.close()

    total_time = time.time() - start_time
    print(f"SUCCESS! Database created in {total_time:.1f}s. Indexed SQLite DB ready at {DB_PATH}")


if __name__ == "__main__":
    build_database()
