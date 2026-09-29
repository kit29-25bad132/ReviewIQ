import csv
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "product_reviews_dataset.csv"

def validate_dataset():
    if not CSV_PATH.exists():
        print(f"Error: CSV file not found at {CSV_PATH}")
        return False, {}

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    required_cols = [
        "review_id", "product_id", "product_name", "brand", "category", 
        "price_inr", "rating", "review_title", "review_text", "language", 
        "sentiment", "aspects_mentioned", "aspect_sentiments", 
        "verified_purchase", "helpful_votes", "review_date", "word_count"
    ]

    missing_cols = [c for c in required_cols if c not in fieldnames]

    review_ids = [r["review_id"] for r in rows]
    dup_review_ids = [item for item, count in Counter(review_ids).items() if count > 1]

    products = {}
    for r in rows:
        pid = r["product_id"]
        pname = r["product_name"]
        cat = r["category"]
        brand = r["brand"]
        price = r["price_inr"]
        if pid not in products:
            products[pid] = {
                "name": pname,
                "brand": brand,
                "category": cat,
                "price": price,
                "review_count": 0,
            }
        products[pid]["review_count"] += 1

    empty_reviews = [r["review_id"] for r in rows if not r.get("review_text") or not r.get("review_text").strip()]

    invalid_ratings = []
    for r in rows:
        val = r.get("rating", "")
        try:
            r_int = int(float(val))
            if r_int < 1 or r_int > 5:
                invalid_ratings.append(r["review_id"])
        except ValueError:
            invalid_ratings.append(r["review_id"])

    # Duplicate row check
    row_tuples = [tuple(r.get(c, "") for c in fieldnames) for r in rows]
    dup_rows = len(row_tuples) - len(set(row_tuples))

    # Duplicate review texts check
    review_texts = [r.get("review_text", "").strip().lower() for r in rows]
    text_counts = Counter(review_texts)
    dup_texts = {text: count for text, count in text_counts.items() if count > 1}

    # Missing values check across all required columns
    missing_values = {col: 0 for col in required_cols}
    for r in rows:
        for col in required_cols:
            if not r.get(col) or not str(r.get(col)).strip():
                missing_values[col] += 1

    report = {
        "csv_path": str(CSV_PATH),
        "total_rows": len(rows),
        "columns_present": len(missing_cols) == 0,
        "missing_columns": missing_cols,
        "unique_products": len(products),
        "products": products,
        "unique_reviews": len(set(review_ids)),
        "duplicate_review_ids": dup_review_ids,
        "duplicate_rows": dup_rows,
        "empty_reviews": len(empty_reviews),
        "invalid_ratings": len(invalid_ratings),
        "duplicate_review_texts_count": len(dup_texts),
        "missing_values": missing_values,
    }

    print("==================================================")
    print("REVIEWIQ DATASET VALIDATION REPORT")
    print("==================================================")
    print(f"Dataset File: {CSV_PATH.name}")
    print(f"Total Rows: {report['total_rows']}")
    print(f"Required Columns Valid: {report['columns_present']}")
    print(f"Unique Products: {report['unique_products']}")
    print(f"Unique Review IDs: {report['unique_reviews']}")
    print(f"Duplicate Rows: {report['duplicate_rows']}")
    print(f"Duplicate Review IDs: {len(report['duplicate_review_ids'])}")
    print(f"Empty Review Texts: {report['empty_reviews']}")
    print(f"Invalid Ratings: {report['invalid_ratings']}")
    print(f"Duplicate Review Texts: {report['duplicate_review_texts_count']}")
    print(f"Missing Values: {report['missing_values']}")
    print("--------------------------------------------------")
    print("Products in Dataset:")
    for pid in sorted(products.keys()):
        p = products[pid]
        print(f"  [{pid}] {p['name']} ({p['category']}, {p['brand']}) - {p['review_count']} reviews (Rs. {p['price']})")
    print("==================================================")

    is_valid = (
        len(missing_cols) == 0
        and len(dup_review_ids) == 0
        and dup_rows == 0
        and len(empty_reviews) == 0
        and len(invalid_ratings) == 0
    )

    return is_valid, report

if __name__ == "__main__":
    validate_dataset()
