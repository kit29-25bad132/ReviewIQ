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
    contradictory_metadata_count: int = 0
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

        # Check 1 — Empty dataset (FAIL). First check: an empty dataset
        # short-circuits everything downstream (downstream analyzers handle
        # empty input safely and report zeros).
        EMPTY_DATASET_THRESHOLD = 0
        if total_reviews <= EMPTY_DATASET_THRESHOLD:
            hard_failures.append("EMPTY_DATASET: zero reviews loaded — dataset is empty")

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
        CONTRADICTION_FAIL_PCT = 5.0
        NEAR_DUP_FAIL_PCT = 5.0
        if trust_analysis["orphan_reviews_count"] > 0:
            hard_failures.append(f"Orphan reviews detected: {trust_analysis['orphan_reviews_count']} reviews have no matching product.")

        if trust_analysis["provenance_coverage_pct"] < 100.0:
            hard_failures.append(f"Incomplete provenance coverage: {trust_analysis['provenance_coverage_pct']}% (must be 100%).")

        # Check 2 — Contradiction rate (FAIL above 5%)
        contradiction_pct = (trust_analysis["contradictory_metadata_count"] / total_reviews * 100
                             if total_reviews > 0 else 0.0)
        if contradiction_pct > CONTRADICTION_FAIL_PCT:
            hard_failures.append(
                f"CONTRADICTION_RATE: {contradiction_pct:.1f}% exceeds {CONTRADICTION_FAIL_PCT}% threshold"
            )

        # Check 3 — Near-duplicate rate (FAIL above 5%)
        if near_dups["percentage"] > NEAR_DUP_FAIL_PCT:
            hard_failures.append(
                f"NEAR_DUPLICATE_RATE: {near_dups['percentage']:.1f}% exceeds {NEAR_DUP_FAIL_PCT}% threshold"
            )

        # Check 4 — Exact duplicates (FAIL; formerly a warning)
        if exact_dups["count"] > 0:
            hard_failures.append(
                f"EXACT_DUPLICATES: {exact_dups['count']} identical review texts found"
            )

        if template_reps["count"] > 0:
            warnings.append(f"Template repetition detected in {template_reps['count']} reviews ({template_reps['percentage']}%)")

        # Compute Gate Status
        gate_status = "FAIL" if hard_failures else "PASS"
        passed = (gate_status == "PASS")

        # Deterministic ordering: the profiler sorts distributions by review
        # count, so tied rows come back in arbitrary order between runs.
        # Sort by the distribution key here so identical input always yields
        # byte-identical report output.
        category_distribution = sorted(
            profiling["category_distribution"], key=lambda row: row["category"]
        )
        brand_distribution = sorted(
            profiling["brand_distribution"], key=lambda row: row["brand"]
        )

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
            contradictory_metadata_count=trust_analysis["contradictory_metadata_count"],
            provenance_coverage_pct=trust_analysis["provenance_coverage_pct"],
            trustworthiness_score=trust_analysis["trustworthiness_score"],
            rating_distribution=profiling["rating_distribution"],
            product_distribution=profiling["products_summary"],
            category_distribution=category_distribution,
            brand_distribution=brand_distribution,
            review_length_statistics=profiling["review_length_statistics"],
            sentiment_distribution=profiling["sentiment_distribution"],
            hard_failure_reasons=hard_failures,
            warnings=warnings,
        )

        return passed, report


quality_gate_runner = QualityGateRunner()
