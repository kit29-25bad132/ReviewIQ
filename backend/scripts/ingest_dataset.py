import csv
import sqlite3
import time
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "product_reviews_dataset.csv"
DB_PATH = DATA_DIR / "ecommerce_reviews.db"
BACKUP_DB_PATH = DATA_DIR / "ecommerce_reviews_backup.db"


def ingest_new_dataset():
    if not CSV_PATH.exists():
        # Check parent folder as fallback
        alt_path = BASE_DIR.parent / "product_reviews_dataset.csv"
        if alt_path.exists():
            shutil.copy(alt_path, CSV_PATH)
        else:
            raise FileNotFoundError(f"New dataset CSV not found at {CSV_PATH}")

    print(f"Starting ingestion of new dataset from {CSV_PATH}...")
    start_time = time.time()

    # 1. Backup old database if exists
    if DB_PATH.exists():
        try:
            shutil.copy(DB_PATH, BACKUP_DB_PATH)
            print(f"Backed up old database to {BACKUP_DB_PATH}")
        except Exception as e:
            print(f"Backup notice: {e}")

        try:
            DB_PATH.unlink()
        except Exception as e:
            print(f"Notice: old DB unlink {e}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fast SQLite pragmas
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA journal_mode = WAL;")

    # 2. Create Reviews Table with full rich schema matching new dataset
    cursor.execute("""
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT UNIQUE NOT NULL,
            product_id TEXT NOT NULL,
            product_title TEXT NOT NULL,
            brand TEXT,
            category TEXT,
            price_inr REAL,
            rating INTEGER NOT NULL,
            review_title TEXT,
            review_text TEXT NOT NULL,
            language TEXT,
            sentiment TEXT NOT NULL,
            aspects_mentioned TEXT,
            aspect_sentiments TEXT,
            verified_purchase TEXT,
            helpful_votes INTEGER DEFAULT 0,
            review_date TEXT,
            word_count INTEGER
        );
    """)

    batch = []
    total_rows = 0

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            review_id = row.get("review_id", "").strip()
            product_id = row.get("product_id", "").strip()
            product_name = row.get("product_name", "").strip()
            brand = row.get("brand", "").strip()
            category = row.get("category", "").strip()
            
            try:
                price_inr = float(row.get("price_inr", 0))
            except ValueError:
                price_inr = 0.0

            try:
                rating = int(float(row.get("rating", 0)))
            except ValueError:
                rating = 0

            review_title = row.get("review_title", "").strip()
            review_text = row.get("review_text", "").strip()
            language = row.get("language", "").strip()
            sentiment = row.get("sentiment", "").strip().lower()
            aspects_mentioned = row.get("aspects_mentioned", "").strip()
            aspect_sentiments = row.get("aspect_sentiments", "").strip()
            verified_purchase = row.get("verified_purchase", "").strip()
            
            try:
                helpful_votes = int(float(row.get("helpful_votes", 0)))
            except ValueError:
                helpful_votes = 0

            review_date = row.get("review_date", "").strip()
            
            try:
                word_count = int(float(row.get("word_count", len(review_text.split()))))
            except ValueError:
                word_count = len(review_text.split())

            if not review_id or not product_id or not product_name or not review_text:
                continue

            batch.append((
                review_id,
                product_id,
                product_name,
                brand,
                category,
                price_inr,
                rating,
                review_title,
                review_text,
                language,
                sentiment,
                aspects_mentioned,
                aspect_sentiments,
                verified_purchase,
                helpful_votes,
                review_date,
                word_count
            ))
            total_rows += 1

    cursor.executemany("""
        INSERT INTO reviews (
            review_id, product_id, product_title, brand, category, price_inr,
            rating, review_title, review_text, language, sentiment,
            aspects_mentioned, aspect_sentiments, verified_purchase,
            helpful_votes, review_date, word_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)

    conn.commit()
    print(f"Reviews table complete: {total_rows} rows inserted in {time.time()-start_time:.2f}s.")

    # 3. Build Products table pre-aggregated from actual reviews
    cursor.execute("""
        CREATE TABLE products AS
        SELECT
            product_id,
            product_title,
            LOWER(TRIM(product_title)) AS normalized_title,
            brand,
            category,
            MAX(price_inr) AS price_inr,
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
        GROUP BY product_id, product_title, brand, category;
    """)

    # 4. Indexes for fast retrieval, filtering, and search
    cursor.execute("CREATE INDEX idx_products_pid ON products(product_id);")
    cursor.execute("CREATE INDEX idx_products_norm_title ON products(normalized_title);")
    cursor.execute("CREATE INDEX idx_products_title ON products(product_title);")
    cursor.execute("CREATE INDEX idx_products_cat ON products(category);")
    cursor.execute("CREATE INDEX idx_reviews_rid ON reviews(review_id);")
    cursor.execute("CREATE INDEX idx_reviews_product_id ON reviews(product_id);")
    cursor.execute("CREATE INDEX idx_reviews_pid_rating ON reviews(product_id, rating);")
    cursor.execute("CREATE INDEX idx_reviews_pid_sentiment ON reviews(product_id, sentiment);")

    conn.commit()

    # 5. Verification Queries
    cursor.execute("SELECT COUNT(*) FROM reviews;")
    cnt_reviews = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT review_id) FROM reviews;")
    cnt_distinct_rev = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT product_id) FROM reviews;")
    cnt_distinct_prod = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products;")
    cnt_products = cursor.fetchone()[0]

    # Verify no orphan reviews
    cursor.execute("""
        SELECT COUNT(*) FROM reviews r
        WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = r.product_id);
    """)
    orphan_count = cursor.fetchone()[0]

    conn.close()

    total_time = time.time() - start_time
    print("==================================================")
    print("DATABASE INGESTION & VERIFICATION REPORT")
    print("==================================================")
    print(f"Database File: {DB_PATH}")
    print(f"Total Reviews: {cnt_reviews}")
    print(f"Distinct Review IDs: {cnt_distinct_rev}")
    print(f"Distinct Product IDs: {cnt_distinct_prod}")
    print(f"Products in Products Table: {cnt_products}")
    print(f"Orphan Reviews: {orphan_count}")
    print(f"Total Execution Time: {total_time:.2f}s")
    print("==================================================")

    assert cnt_reviews == 1500, f"Expected 1500 reviews, got {cnt_reviews}"
    assert cnt_distinct_rev == 1500, f"Expected 1500 distinct review IDs, got {cnt_distinct_rev}"
    assert cnt_distinct_prod == 20, f"Expected 20 distinct products, got {cnt_distinct_prod}"
    assert orphan_count == 0, f"Found {orphan_count} orphan reviews"

    return {
        "reviews": cnt_reviews,
        "distinct_reviews": cnt_distinct_rev,
        "products": cnt_products,
        "orphan_count": orphan_count,
    }


if __name__ == "__main__":
    ingest_new_dataset()
