"""Run Phase 2 Quality Gate on the canonical product_reviews_dataset.csv."""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.quality.quality_gate import quality_gate_runner

def main():
    csv_path = ROOT_DIR / "product_reviews_dataset.csv"
    if not csv_path.exists():
        csv_path = BASE_DIR / "data" / "product_reviews_dataset.csv"

    print(f"Evaluating dataset quality for {csv_path}...")
    passed, report = quality_gate_runner.evaluate_csv(csv_path)

    print("\n==================================================")
    print(f" REVIEWIQ DATA QUALITY GATE REPORT")
    print("==================================================")
    print(f"GATE STATUS: {report.status}")
    print(f"Dataset Version: {report.dataset_version}")
    print(f"Total Rows: {report.total_rows}")
    print(f"Total Products: {report.total_products}")
    print(f"Total Reviews: {report.total_reviews}")
    print(f"Exact Duplicates: {report.exact_duplicate_count} ({report.exact_duplicate_pct}%)")
    print(f"Normalized Duplicates: {report.normalized_duplicate_count} ({report.normalized_duplicate_pct}%)")
    print(f"Near Duplicates: {report.near_duplicate_count} ({report.near_duplicate_pct}%)")
    print(f"Template Repetition: {report.template_repetition_count} ({report.template_repetition_pct}%)")
    print(f"Orphan Reviews: {report.orphan_reviews_count}")
    print(f"Provenance Coverage: {report.provenance_coverage_pct}%")
    print(f"Trustworthiness Score: {report.trustworthiness_score}/100")
    print(f"\nRating Distribution:")
    for r in report.rating_distribution:
        print(f"  {r['rating']} Stars: {r['count']} ({r['percentage']}%)")
    print("\nCategories (5):")
    for c in report.category_distribution:
        print(f"  {c['category']}: {c['review_count']} reviews across {c['product_count']} products (Avg: {c['avg_rating']} stars)")
    print(f"\nBrands ({len(report.brand_distribution)}):")
    for b in report.brand_distribution:
        print(f"  {b['brand']}: {b['review_count']} reviews across {b['product_count']} products (Avg: {b['avg_rating']} stars)")
    
    if report.hard_failure_reasons:
        print(f"\nHARD FAILURES:")
        for h in report.hard_failure_reasons:
            print(f"  - {h}")
    
    if report.warnings:
        print(f"\nWARNINGS / SIGNALS:")
        for w in report.warnings:
            print(f"  - {w}")

    # Save to json file for persistence
    report_file = BASE_DIR / "data" / "data_quality_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"\nSaved machine-readable report to {report_file}")

if __name__ == "__main__":
    main()
