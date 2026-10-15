"""Pandera executable contracts for ReviewIQ dataset quality validation."""

from typing import Optional, Tuple, Dict, Any
import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema


def create_dataset_schema() -> DataFrameSchema:
    """Returns a strict executable Pandera schema for product reviews dataset."""
    return DataFrameSchema(
        columns={
            "review_id": Column(
                pa.String,
                checks=[
                    Check(lambda s: s.str.strip().str.len() > 0, error="review_id must not be empty"),
                    Check(lambda s: s.is_unique, error="review_id must be unique"),
                ],
                nullable=False,
                coerce=True,
            ),
            "product_id": Column(
                pa.String,
                checks=[
                    Check(lambda s: s.str.strip().str.len() > 0, error="product_id must not be empty"),
                ],
                nullable=False,
                coerce=True,
            ),
            "product_name": Column(
                pa.String,
                checks=[
                    Check(lambda s: s.str.strip().str.len() > 0, error="product_name must not be empty"),
                ],
                nullable=False,
                coerce=True,
            ),
            "brand": Column(
                pa.String,
                checks=[
                    Check(lambda s: s.str.strip().str.len() > 0, error="brand must not be empty"),
                ],
                nullable=False,
                coerce=True,
            ),
            "category": Column(
                pa.String,
                checks=[
                    Check(lambda s: s.str.strip().str.len() > 0, error="category must not be empty"),
                ],
                nullable=False,
                coerce=True,
            ),
            "rating": Column(
                pa.Int,
                checks=[
                    Check.in_range(1, 5, include_min=True, include_max=True, error="rating must be between 1 and 5"),
                ],
                nullable=False,
                coerce=True,
            ),
            "review_text": Column(
                pa.String,
                checks=[
                    Check(lambda s: s.str.strip().str.len() > 0, error="review_text must not be empty or whitespace-only"),
                ],
                nullable=False,
                coerce=True,
            ),
            "sentiment": Column(
                pa.String,
                checks=[
                    Check.isin(["positive", "negative", "neutral", "mixed"], error="sentiment must be valid"),
                ],
                nullable=False,
                coerce=True,
            ),
        },
        strict=False,  # Allow extra optional columns like price_inr, review_title, etc.
        coerce=True,
    )


def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, Optional[str], Optional[pd.DataFrame]]:
    """Executes Pandera validation against the dataframe. Returns (is_valid, error_message, validated_df)."""
    schema = create_dataset_schema()
    try:
        validated_df = schema.validate(df, lazy=True)
        return True, None, validated_df
    except pa.errors.SchemaErrors as exc:
        return False, str(exc.failure_cases), None
    except Exception as exc:
        return False, str(exc), None
