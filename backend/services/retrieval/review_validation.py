"""Review validation for the embedding pipeline.

Establishes a predictable internal representation (``ValidatedReview``) and
returns explicit outcomes instead of raising on bad records, so the indexing
layer can report accepted / duplicate / invalid counts deterministically.

Accepts mappings (dict rows) or existing typed objects (``DatasetReview``,
``ReviewItem``, ``ValidatedReview``) via attribute lookup. Never manufactures
review content.
"""

from datetime import datetime
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from services.retrieval.contracts import (
    MAX_REVIEW_TEXT_LENGTH,
    RejectedReview,
    ValidatedReview,
    ValidationOutcome,
    ValidationReport,
)

# Recognized field aliases across the two existing data sources
# (dataset_service.DatasetReview and ecommerce ReviewItem).
_REVIEW_ID_KEYS = ("review_id", "id", "reviewId")
_PRODUCT_ID_KEYS = ("product_id", "asin", "productId")
_REVIEW_TEXT_KEYS = ("review_text", "reviewText", "text", "review")
_RATING_KEYS = ("rating", "actual_rating", "overall")
_TITLE_KEYS = ("title", "product_title", "summary")
_SOURCE_KEYS = ("source",)
_DATE_KEYS = ("review_date", "reviewTime", "date")


def _lookup(raw: Any, keys: Tuple[str, ...]) -> Tuple[bool, Any]:
    """Return (present, value) for the first matching key/attribute."""
    if isinstance(raw, Mapping):
        for key in keys:
            if key in raw:
                return True, raw[key]
        return False, None
    for key in keys:
        if hasattr(raw, key):
            return True, getattr(raw, key)
    return False, None


def _identifier(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """Coerce a scalar identifier to a stripped string; reject containers."""
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, "identifier must be a string or number"
    if isinstance(value, str):
        return value.strip() or None, None
    if isinstance(value, (int, float)):
        return str(value), None
    return None, "identifier must be a string or number"


def _parse_rating(value: Any) -> Tuple[Optional[int], Optional[str]]:
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, "rating must be an integer 1-5"
    if isinstance(value, int):
        rating = value
    elif isinstance(value, float):
        if not value.is_integer():
            return None, "rating must be a whole number 1-5"
        rating = int(value)
    elif isinstance(value, str):
        try:
            rating = int(float(value.strip()))
        except (TypeError, ValueError):
            return None, "rating is not numeric"
    else:
        return None, "rating must be an integer 1-5"
    if not 1 <= rating <= 5:
        return None, "rating out of range 1-5"
    return rating, None


def _parse_datetime(value: Any) -> Tuple[Optional[datetime], Optional[str]]:
    if value is None:
        return None, None
    if isinstance(value, datetime):
        return value, None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None, None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")), None
        except ValueError:
            return None, "review_date is not a valid ISO date"
    return None, "review_date must be an ISO string or datetime"


def _optional_str(value: Any) -> Tuple[Optional[str], Optional[str]]:
    if value is None:
        return None, None
    if isinstance(value, str):
        return value.strip() or None, None
    return None, "expected a string"


def _reject(
    outcome: ValidationOutcome,
    reason: str,
    review_id: Optional[str] = None,
    product_id: Optional[str] = None,
) -> RejectedReview:
    return RejectedReview(
        outcome=outcome, reason=reason, review_id=review_id, product_id=product_id
    )


def validate_review(raw: Any) -> Tuple[Optional[ValidatedReview], Optional[RejectedReview]]:
    """Validate one record, returning (validated, rejected) with exactly one set."""
    if raw is None:
        return None, _reject(ValidationOutcome.INVALID_MALFORMED, "record is null")
    if not isinstance(raw, Mapping) and not hasattr(raw, "__dict__") and not hasattr(
        raw, "review_text"
    ):
        return None, _reject(
            ValidationOutcome.INVALID_MALFORMED,
            f"unsupported record type: {type(raw).__name__}",
        )

    present_id, raw_id = _lookup(raw, _REVIEW_ID_KEYS)
    present_pid, raw_pid = _lookup(raw, _PRODUCT_ID_KEYS)
    review_id, err = _identifier(raw_id) if present_id else (None, None)
    if err:
        return None, _reject(ValidationOutcome.INVALID_MALFORMED, err)
    product_id, err = _identifier(raw_pid) if present_pid else (None, None)
    if err:
        return None, _reject(ValidationOutcome.INVALID_MALFORMED, err, review_id)

    present_text, raw_text = _lookup(raw, _REVIEW_TEXT_KEYS)
    if not present_text or raw_text is None:
        return None, _reject(
            ValidationOutcome.INVALID_MISSING_TEXT, "review_text is missing", review_id
        )
    if not isinstance(raw_text, str):
        return None, _reject(
            ValidationOutcome.INVALID_MALFORMED,
            "review_text must be a string",
            review_id,
        )
    review_text = raw_text.strip()
    if not review_text:
        return None, _reject(
            ValidationOutcome.INVALID_EMPTY_TEXT,
            "review_text is empty or whitespace only",
            review_id,
        )
    if len(review_text) > MAX_REVIEW_TEXT_LENGTH:
        return None, _reject(
            ValidationOutcome.INVALID_TEXT_TOO_LONG,
            f"review_text exceeds {MAX_REVIEW_TEXT_LENGTH} characters",
            review_id,
        )

    present_rating, raw_rating = _lookup(raw, _RATING_KEYS)
    rating, err = _parse_rating(raw_rating) if present_rating else (None, None)
    if err:
        return None, _reject(ValidationOutcome.INVALID_METADATA, err, review_id)

    present_title, raw_title = _lookup(raw, _TITLE_KEYS)
    title, err = _optional_str(raw_title) if present_title else (None, None)
    if err:
        return None, _reject(ValidationOutcome.INVALID_METADATA, err, review_id)

    present_source, raw_source = _lookup(raw, _SOURCE_KEYS)
    source, err = _optional_str(raw_source) if present_source else (None, None)
    if err:
        return None, _reject(ValidationOutcome.INVALID_METADATA, err, review_id)

    present_date, raw_date = _lookup(raw, _DATE_KEYS)
    review_date, err = _parse_datetime(raw_date) if present_date else (None, None)
    if err:
        return None, _reject(ValidationOutcome.INVALID_METADATA, err, review_id)

    return (
        ValidatedReview(
            review_id=review_id,
            product_id=product_id,
            review_text=review_text,
            rating=rating,
            title=title,
            source=source,
            review_date=review_date,
        ),
        None,
    )


def validate_reviews(records: Sequence[Any]) -> ValidationReport:
    """Validate many records, preserving input order within each outcome list."""
    accepted: List[ValidatedReview] = []
    rejected: List[RejectedReview] = []
    for record in records:
        validated, rejected_review = validate_review(record)
        if validated is not None:
            accepted.append(validated)
        elif rejected_review is not None:
            rejected.append(rejected_review)
    return ValidationReport(accepted=tuple(accepted), rejected=tuple(rejected))
