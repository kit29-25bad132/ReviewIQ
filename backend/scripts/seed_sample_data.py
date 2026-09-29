from pathlib import Path
from scripts.ingest_dataset import ingest_new_dataset

def seed_database():
    print("Seeding database using authoritative product_reviews_dataset.csv...")
    ingest_new_dataset()

if __name__ == "__main__":
    seed_database()
