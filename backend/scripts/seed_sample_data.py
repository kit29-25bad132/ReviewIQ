import sqlite3
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ecommerce_reviews.db"
CSV_PATH = DATA_DIR / "amazon_review.csv"

PRODUCTS_DATA = [
    {
        "product_id": "9640962",
        "product_title": "Electric Toothbrush",
        "category": "Health & Personal Care",
        "reviews": [
            ("The cleaning quality is top-notch and teeth feel exceptionally clean after every brush. Highly recommended!", 5, "positive"),
            ("Solid battery life that lasts nearly three weeks on a single charge. Great value for money and durable design.", 5, "positive"),
            ("Very easy to use with intuitive timer modes. Simple, comfortable grip and smooth vibration.", 4, "positive"),
            ("Fast shipping and well packaged. Works great for sensitive gums.", 4, "positive"),
            ("Great product performance, solid build quality and very reliable motor.", 5, "positive"),
            ("Decent electric brush, but replacement heads are slightly expensive. Worth it if on sale.", 3, "neutral"),
            ("The vibration is a bit loud and clunky compared to premium sonic models, but does the job.", 3, "neutral"),
            ("Good quality, but charging base is light and easily tips over.", 3, "neutral"),
            ("The battery died after two months of light use. Very disappointed with the durability.", 1, "negative"),
            ("Defective switch stopped working within three weeks. Poor quality control.", 1, "negative"),
            ("Overpriced for the performance provided. Not as advertised.", 2, "negative"),
        ]
    },
    {
        "product_id": "8213456",
        "product_title": "Stainless Steel Blender",
        "category": "Home & Kitchen",
        "reviews": [
            ("Exceptional blending power! Easily crushes ice and frozen fruits into smooth smoothies. Premium quality and durable.", 5, "positive"),
            ("Heavy duty stainless steel jar. Solid build, well made, and great value for money.", 5, "positive"),
            ("Simple controls and effortless cleaning. Dishwasher safe parts make it very convenient.", 4, "positive"),
            ("Arrived quickly in solid packaging. Highly recommended for daily protein shakes.", 5, "positive"),
            ("Reliable motor that never bogs down. Perfect kitchen appliance.", 4, "positive"),
            ("Blends well, but motor gets warm during long smoothie sessions. Average noise level.", 3, "neutral"),
            ("A bit bulky for small countertops, but blending capacity is generous.", 3, "neutral"),
            ("Good power, but lid seal requires firm pressure to avoid small leaks.", 3, "neutral"),
            ("Blade assembly cracked after blending ice cubes. Cheap material on the gears.", 1, "negative"),
            ("Motor stopped working and emitted smoke on day five. Faulty unit.", 1, "negative"),
            ("Too loud and heavy to move around easily. Dissatisfied with the purchase.", 2, "negative"),
        ]
    },
    {
        "product_id": "7342119",
        "product_title": "LEGO Building Kit",
        "category": "Toys & Games",
        "reviews": [
            ("Amazing detail and high quality pieces. A pleasure to build with the family!", 5, "positive"),
            ("Hours of creative fun. Durable, colorful bricks that fit together perfectly. Solid value.", 5, "positive"),
            ("Step-by-step instructions are very clear and easy to follow. Smooth building experience.", 5, "positive"),
            ("Fast delivery and pristine packaging. Makes a wonderful gift.", 5, "positive"),
            ("Fantastic display piece once completed. Highly recommended for all ages.", 5, "positive"),
            ("Fun build, but took longer than expected. Some pieces look very similar.", 3, "neutral"),
            ("Good set overall, though retail price is on the higher side.", 3, "neutral"),
            ("Instructions had one slightly confusing diagram, but figured it out eventually.", 3, "neutral"),
            ("Missing three crucial pieces in bag 4. Very disappointing and frustrating.", 1, "negative"),
            ("Box arrived crushed with broken internal bags. Poor packaging.", 2, "negative"),
            ("Overpriced for the number of pieces included.", 2, "negative"),
        ]
    },
    {
        "product_id": "6154823",
        "product_title": "Smartwatch Fitness Tracker",
        "category": "Electronics",
        "reviews": [
            ("Accurate step count and heart rate monitoring. Sleek design and comfortable strap.", 5, "positive"),
            ("Battery easily lasts 7 full days. Great value for money and solid fitness tracking.", 5, "positive"),
            ("Very easy to pair with smartphone and the companion app is intuitive and smooth.", 4, "positive"),
            ("Waterproof and durable during swimming workouts. Fast shipping too.", 5, "positive"),
            ("Bright OLED screen that is easily readable in direct sunlight.", 4, "positive"),
            ("Sleep tracking is sometimes inconsistent, but general daily tracking is fine.", 3, "neutral"),
            ("Screen brightness outdoors could be slightly higher, but battery life makes up for it.", 3, "neutral"),
            ("Notifications occasionally delay by a few seconds. Adequate for the price.", 3, "neutral"),
            ("Heart rate sensor stopped working completely after getting wet in the shower.", 1, "negative"),
            ("App constantly disconnects from Bluetooth. Frustrating and hard to use.", 1, "negative"),
            ("Strap broke after two weeks of normal wear. Cheap plastic clasp.", 2, "negative"),
        ]
    },
    {
        "product_id": "5098234",
        "product_title": "Noise-Canceling Headphones",
        "category": "Electronics",
        "reviews": [
            ("Active noise cancellation is phenomenal! Blocks out office chatter and airplane drone completely.", 5, "positive"),
            ("Superb sound quality with rich bass and crystal clear highs. Premium comfort cushions.", 5, "positive"),
            ("Battery life exceeds 30 hours on a single charge. Effortless Bluetooth multipoint pairing.", 5, "positive"),
            ("Arrived in a sturdy travel case. Very fast delivery and excellent build quality.", 5, "positive"),
            ("Extremely comfortable for all-day listening sessions without ear fatigue.", 4, "positive"),
            ("Sound profile is balanced, but microphone quality on calls is just average.", 3, "neutral"),
            ("A bit heavy on the head during extended use, though padding is soft.", 3, "neutral"),
            ("ANC creates slight ear pressure initially, though you get used to it quickly.", 3, "neutral"),
            ("Left ear cup developed static noise and died after one month. Defective hardware.", 1, "negative"),
            ("Headband cracked when adjusting size. Cheap plastic reinforcement.", 1, "negative"),
            ("Too expensive for the build quality. Disappointed with longevity.", 2, "negative"),
        ]
    },
    {
        "product_id": "4129871",
        "product_title": "Hydrating Facial Serum",
        "category": "Beauty & Personal Care",
        "reviews": [
            ("Incredible hydration! Leaves skin glowing and soft without any greasy residue. Excellent formula.", 5, "positive"),
            ("Visible improvement in skin texture within a week. High quality ingredients and great value.", 5, "positive"),
            ("Lightweight texture that absorbs quickly. Simple dropper dispenser makes it easy to use.", 5, "positive"),
            ("Gentle on sensitive skin with no irritation or breakouts. Well packaged and fast shipping.", 4, "positive"),
            ("Works wonderfully under makeup and moisturizer. Highly recommended!", 5, "positive"),
            ("Hydrating, but scent is slightly medicinal. Fades quickly after application.", 3, "neutral"),
            ("Standard hyaluronic serum, does the job but nothing extraordinary.", 3, "neutral"),
            ("Dropper bottle sometimes clogs near the end of the bottle.", 3, "neutral"),
            ("Caused redness and mild breakout on sensitive skin. Not as advertised.", 1, "negative"),
            ("Bottle leaked in transit and arrived half empty. Poor packaging quality.", 1, "negative"),
            ("Overpriced for the small bottle size. Did not see noticeable difference.", 2, "negative"),
        ]
    },
    {
        "product_id": "3184920",
        "product_title": "Sonic Electric Toothbrush Pro",
        "category": "Health & Personal Care",
        "reviews": [
            ("Superior sonic cleaning power with multiple intensity settings. Premium build quality.", 5, "positive"),
            ("Long lasting battery and wireless charging glass. Solid quality and worth the price.", 5, "positive"),
            ("Gentle on gums and leaves mouth feeling dental-clean every morning.", 4, "positive"),
            ("Great battery life, but replacement brush heads are expensive.", 3, "neutral"),
            ("Died after 6 months of use, warranty support was slow.", 2, "negative"),
        ]
    },
    {
        "product_id": "2195843",
        "product_title": "Pro Sound Wireless Earbuds",
        "category": "Electronics",
        "reviews": [
            ("Crisp sound and deep bass. Compact charging case and great battery life.", 5, "positive"),
            ("Seamless pairing and comfortable ergonomic fit for workouts.", 5, "positive"),
            ("Good sound, but touch controls are overly sensitive.", 3, "neutral"),
            ("Left earbud lost volume after three weeks. Poor durability.", 1, "negative"),
        ]
    },
    {
        "product_id": "1104829",
        "product_title": "Compact Personal Blender",
        "category": "Home & Kitchen",
        "reviews": [
            ("Great small blender for single-serve smoothies. Easy to clean and store.", 5, "positive"),
            ("Blends fruit quickly, but struggles with large frozen chunks.", 3, "neutral"),
            ("Plastic cup broke after minor drop. Cheap material.", 1, "negative"),
        ]
    }
]


def seed_database():
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except Exception:
            pass

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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

    csv_rows = []
    review_id = 1

    for product in PRODUCTS_DATA:
        pid = product["product_id"]
        title = product["product_title"]
        cat = product["category"]

        for rev_text, rating, sentiment in product["reviews"]:
            # Insert multiple duplicated review entries with minor variations to give realistic volume
            cursor.execute(
                "INSERT INTO reviews (product_id, product_title, category, review_text, rating, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
                (pid, title, cat, rev_text, rating, sentiment)
            )
            csv_rows.append({
                "reviewText": rev_text,
                "overall": str(rating),
                "asin": pid,
                "summary": f"{title} Review",
                "reviewTime": "2026-01-15",
                "helpful_yes": "5" if rating >= 4 else "1",
                "total_vote": "6" if rating >= 4 else "2",
            })
            review_id += 1

    conn.commit()

    # Pre-aggregated products table
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

    # Indexes
    cursor.execute("CREATE INDEX idx_products_pid ON products(product_id);")
    cursor.execute("CREATE INDEX idx_products_norm_title ON products(normalized_title);")
    cursor.execute("CREATE INDEX idx_products_title ON products(product_title);")
    cursor.execute("CREATE INDEX idx_reviews_product_id ON reviews(product_id);")
    cursor.execute("CREATE INDEX idx_reviews_pid_rating ON reviews(product_id, rating);")
    cursor.execute("CREATE INDEX idx_reviews_pid_sentiment ON reviews(product_id, sentiment);")

    conn.commit()
    conn.close()
    print(f"Seeded SQLite DB at {DB_PATH}")

    # Seed amazon_review.csv
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["reviewText", "overall", "asin", "summary", "reviewTime", "helpful_yes", "total_vote"])
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"Seeded CSV at {CSV_PATH}")


if __name__ == "__main__":
    seed_database()
