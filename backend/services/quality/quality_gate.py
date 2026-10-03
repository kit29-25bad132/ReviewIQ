"""Data Quality Gate and Machine-Readable Report Generator for ReviewIQ."""

import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from pydantic import BaseModel, Field

from services.quality.duckdb_profiler import duckdb_profiler
from services.quality.duplicate_detector import duplicate_detector
from services.quality.pandera_contracts import validate_dataframe
from services.quality.trustworthiness_checker import trustworthiness_checker


class DataQualityReport(BaseModel):
    """Machine-readable dataset quality report."""
    dataset_version: str
    ingestion_run_id: Optional[str] = None
    validation_version: str = "v3.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str  # "PASS" or "FAIL"
    total_rows: int
    total_products: int
    total_reviews: int
    exact_duplicate_count: int = 0
    exact_duplicate_pct: float = 0.0
    normalized_duplicate_count: int = 0
    normalized_duplicate_pct: float = 0.0
    near_duplicate_count: int = 0
    near_duplicate_pct: float = 0.0
    template_repetition_count: int = 0
    template_repetition_pct: float = 0.0
    missing_values_count: int = 0
    invalid_ratings_count: int = 0
    orphan_reviews_count: int = 0
    provenance_coverage_pct: float = 100.0
    trustworthiness_score: float = 100.0
    rating_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    product_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    category_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    brand_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    review_length_statistics: Dict[str, Any] = Field(default_factory=dict)
    sentiment_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    hard_failure_reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class QualityGateRunner:
    """Executes the complete data quality evaluation and generates audit reports."""

    def evaluate_csv(
        self,
        csv_path: Path,
        dataset_version_tag: Optional[str] = None,
        ingestion_run_id: Optional[str] = None,
    ) -> Tuple[bool, DataQualityReport]:
        if not csv_path.exists():
            raise FileNotFoundError(f"Dataset CSV not found at {csv_path}")

        # Compute SHA256 of file for version tag
        with open(csv_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        version = dataset_version_tag or f"hash_{file_hash[:12]}"

        # 1. Read into pandas for Pandera & schema validation
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        is_pandera_valid, pandera_errors, validated_df = validate_dataframe(df)

        hard_failures = []
        warnings = []

        if not is_pandera_valid:
            hard_failures.append(f"Pandera structural contract violation: {pandera_errors}")

        # 2. DuckDB analytical profiling
        profiling = duckdb_profiler.profile_csv(csv_path)
        counts = profiling["counts"]
        total_rows = counts["total_rows"]
        total_products = counts["unique_products"]
        total_reviews = counts["unique_reviews"]

        # 3. Duplicate analysis
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            records = list(csv.DictReader(f))

        dup_analysis = duplicate_detector.analyze(records)
        exact_dups = dup_analysis["exact_duplicates"]
        norm_dups = dup_analysis["normalized_duplicates"]
        near_dups = dup_analysis["near_duplicates"]
        template_reps = dup_analysis["template_repetitions"]

        # 4. Trustworthiness and provenance check
        valid_pids = set(r.get("product_id", "").strip() for r in records if r.get("product_id"))
        trust_analysis = trustworthiness_checker.check(records, valid_pids)

        # 5. Determine Hard Failures vs Warnings
        if trust_analysis["orphan_reviews_count"] > 0:
            hard_failures.append(f"Orphan reviews detected: {trust_analysis['orphan_reviews_count']} reviews have no matching product.")

        if trust_analysis["provenance_coverage_pct"] < 100.0:
            hard_failures.append(f"Incomplete provenance coverage: {trust_analysis['provenance_coverage_pct']}% (must be 100%).")

        if exact_dups["count"] > 0:
            warnings.append(f"Exact duplicate reviews present: {exact_dups['count']} ({exact_dups['percentage']}%)")

        if template_reps["count"] > 0:
            warnings.append(f"Template repetition detected in {template_reps['count']} reviews ({template_reps['percentage']}%)")

        # Compute Gate Status
        gate_status = "FAIL" if hard_failures else "PASS"
        passed = (gate_status == "PASS")

        report = DataQualityReport(
            dataset_version=version,
            ingestion_run_id=ingestion_run_id,
            status=gate_status,
            total_rows=total_rows,
            total_products=total_products,
            total_reviews=total_reviews,
            exact_duplicate_count=exact_dups["count"],
            exact_duplicate_pct=exact_dups["percentage"],
            normalized_duplicate_count=norm_dups["count"],
            normalized_duplicate_pct=norm_dups["percentage"],
            near_duplicate_count=near_dups["count"],
            near_duplicate_pct=near_dups["percentage"],
            template_repetition_count=template_reps["count"],
            template_repetition_pct=template_reps["percentage"],
            missing_values_count=trust_analysis.get("missing_provenance_count", 0),
            invalid_ratings_count=0 if is_pandera_valid else 1,
            orphan_reviews_count=trust_analysis["orphan_reviews_count"],
            provenance_coverage_pct=trust_analysis["provenance_coverage_pct"],
            trustworthiness_score=trust_analysis["trustworthiness_score"],
            rating_distribution=profiling["rating_distribution"],
            product_distribution=profiling["products_summary"],
            category_distribution=profiling["category_distribution"],
            brand_distribution=profiling["brand_distribution"],
            review_length_statistics=profiling["review_length_statistics"],
            sentiment_distribution=profiling["sentiment_distribution"],
            hard_failure_reasons=hard_failures,
            warnings=warnings,
        )

        return passed, report


quality_gate_runner = QualityGateRunner()
