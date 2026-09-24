import csv
import hashlib
import re
from pathlib import Path
from threading import Lock
from typing import Optional

from models.dataset import DatasetReview


class DatasetUnavailableError(RuntimeError):
    pass


class DatasetService:
    """Loads the supplied CSV once and only exposes cleaned, original records."""

    REQUIRED_COLUMNS = {"reviewText", "overall"}

    def __init__(self) -> None:
        self.path = Path(__file__).resolve().parent.parent / "data" / "amazon_review.csv"
        self._records: Optional[list[DatasetReview]] = None
        self._lock = Lock()

    @staticmethod
    def sentiment_from_rating(rating: int) -> str:
        return "negative" if rating <= 2 else "neutral" if rating == 3 else "positive"

    def records(self) -> list[DatasetReview]:
        if self._records is not None:
            return self._records
        with self._lock:
            if self._records is None:
                self._records = self._load()
        return self._records

    def _load(self) -> list[DatasetReview]:
        if not self.path.is_file():
            raise DatasetUnavailableError("Review dataset could not be loaded. Add amazon_review.csv to backend/data/.")
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            missing = self.REQUIRED_COLUMNS - fields
            if missing:
                raise DatasetUnavailableError(f"Review dataset is missing required columns: {', '.join(sorted(missing))}.")
            records: list[DatasetReview] = []
            for row_number, row in enumerate(reader, start=2):
                text = re.sub(r"\s+", " ", (row.get("reviewText") or "").strip())
                if not text:
                    continue
                try:
                    rating = int(float((row.get("overall") or "").strip()))
                except ValueError:
                    continue
                if not 1 <= rating <= 5:
                    continue
                asin = (row.get("asin") or "").strip() or None
                digest = hashlib.sha256(f"{row_number}|{asin}|{text}".encode()).hexdigest()[:20]
                def integer(name: str) -> Optional[int]:
                    try:
                        value = (row.get(name) or "").strip()
                        return int(float(value)) if value else None
                    except ValueError:
                        return None
                records.append(DatasetReview(
                    id=digest, asin=asin, review_text=text, actual_rating=rating,
                    summary=(row.get("summary") or "").strip() or None,
                    review_date=(row.get("reviewTime") or "").strip() or None,
                    helpful_yes=integer("helpful_yes"), total_vote=integer("total_vote"),
                    actual_sentiment=self.sentiment_from_rating(rating),
                ))
        return records

    def query(self, limit: int, offset: int, search: Optional[str], rating: Optional[int], sentiment: Optional[str], product: Optional[str]):
        records = self.records()
        needle = (search or "").casefold().strip()
        product_needle = (product or "").casefold().strip()
        filtered = [r for r in records if (not needle or needle in r.review_text.casefold() or needle in (r.asin or "").casefold()) and (rating is None or r.actual_rating == rating) and (sentiment is None or r.actual_sentiment == sentiment) and (not product_needle or product_needle in (r.asin or "").casefold())]
        return filtered[offset:offset + limit], len(filtered)


dataset_service = DatasetService()
