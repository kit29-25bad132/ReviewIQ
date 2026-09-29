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

    REQUIRED_COLUMNS_PRODUCT = {"review_text", "rating"}
    REQUIRED_COLUMNS_AMAZON = {"reviewText", "overall"}

    def __init__(self) -> None:
        self.primary_path = Path(__file__).resolve().parent.parent / "data" / "product_reviews_dataset.csv"
        self.legacy_path = Path(__file__).resolve().parent.parent / "data" / "amazon_review.csv"
        self._records: Optional[list[DatasetReview]] = None
        self._lock = Lock()

    @property
    def path(self) -> Path:
        if self.primary_path.is_file():
            return self.primary_path
        if self.legacy_path.is_file():
            return self.legacy_path
        # Check parent folder
        alt = self.primary_path.parent.parent.parent / "product_reviews_dataset.csv"
        if alt.is_file():
            return alt
        return self.primary_path

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
        resolved_path = self.path
        if not resolved_path.is_file():
            raise DatasetUnavailableError(
                f"Review dataset could not be loaded. Add product_reviews_dataset.csv to backend/data/."
            )
        with resolved_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            
            is_new_dataset = "review_text" in fields and "rating" in fields
            is_legacy_dataset = "reviewText" in fields and "overall" in fields

            if not is_new_dataset and not is_legacy_dataset:
                raise DatasetUnavailableError(
                    f"Review dataset is missing required columns. Fields found: {', '.join(sorted(fields))}."
                )

            records: list[DatasetReview] = []
            for row_number, row in enumerate(reader, start=2):
                raw_text = row.get("review_text") or row.get("reviewText") or ""
                text = re.sub(r"\s+", " ", raw_text.strip())
                if not text:
                    continue

                raw_rating = row.get("rating") or row.get("overall") or ""
                try:
                    rating = int(float(str(raw_rating).strip()))
                except ValueError:
                    continue
                if not 1 <= rating <= 5:
                    continue

                review_id = (row.get("review_id") or row.get("id") or "").strip()
                asin = (row.get("product_id") or row.get("asin") or "").strip() or None
                product_name = (row.get("product_name") or row.get("product_title") or "").strip() or None
                summary = (row.get("review_title") or row.get("summary") or "").strip() or None
                review_date = (row.get("review_date") or row.get("reviewTime") or "").strip() or None

                if not review_id:
                    review_id = hashlib.sha256(f"{row_number}|{asin}|{text}".encode()).hexdigest()[:20]

                def integer(keys: list[str]) -> Optional[int]:
                    for k in keys:
                        val = (row.get(k) or "").strip()
                        if val:
                            try:
                                return int(float(val))
                            except ValueError:
                                pass
                    return None

                helpful = integer(["helpful_votes", "helpful_yes"])
                total_votes = integer(["total_votes", "total_vote"])

                explicit_sent = (row.get("sentiment") or "").strip().lower()
                if explicit_sent in ["positive", "neutral", "negative"]:
                    actual_sentiment = explicit_sent
                else:
                    actual_sentiment = self.sentiment_from_rating(rating)

                records.append(
                    DatasetReview(
                        id=review_id,
                        asin=asin,
                        product_name=product_name,
                        review_text=text,
                        actual_rating=rating,
                        summary=summary,
                        review_date=review_date,
                        helpful_yes=helpful,
                        total_vote=total_votes,
                        actual_sentiment=actual_sentiment,
                    )
                )
        return records

    def query(
        self,
        limit: int,
        offset: int,
        search: Optional[str],
        rating: Optional[int],
        sentiment: Optional[str],
        product: Optional[str],
    ):
        records = self.records()
        needle = (search or "").casefold().strip()
        product_needle = (product or "").casefold().strip()
        filtered = [
            r
            for r in records
            if (
                not needle
                or needle in r.review_text.casefold()
                or needle in (r.asin or "").casefold()
                or needle in (r.product_name or "").casefold()
            )
            and (rating is None or r.actual_rating == rating)
            and (sentiment is None or r.actual_sentiment == sentiment)
            and (
                not product_needle
                or product_needle in (r.asin or "").casefold()
                or product_needle in (r.product_name or "").casefold()
            )
        ]
        return filtered[offset : offset + limit], len(filtered)


dataset_service = DatasetService()
