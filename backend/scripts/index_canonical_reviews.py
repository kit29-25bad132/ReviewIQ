"""Safe canonical embedding indexing workflow for ReviewIQ.

Dry-run (default): read-only plan — zero provider calls, zero database writes.
    python backend/scripts/index_canonical_reviews.py --dry-run

Bounded run (explicit limit REQUIRED; never expands to the full corpus):
    python backend/scripts/index_canonical_reviews.py --run --limit 10 [--offset 0]

Resume an interrupted run by re-invoking with the next offset; already-indexed
fingerprints are skipped automatically, so reruns are duplicate-free.
Aborts (exit 2) on quota/credential errors instead of burning provider quota.
"""

import argparse
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.retrieval.canonical_indexing import (
    plan_canonical_index,
    run_canonical_index,
)
from services.catalog.catalog_service import canonical_catalog
from services.embeddings.registry import resolve_embedding_model_spec
from services.embeddings.providers.gemini import GeminiEmbeddingProvider
from services.embeddings.service import EmbeddingService
from services.retrieval.preprocessing import preprocess_review_text
from services.retrieval.postgres_vector_repository import PostgresVectorRepository
from services.retrieval.indexing_service import ReviewIndexingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def build_services():
    spec = resolve_embedding_model_spec()
    provider = GeminiEmbeddingProvider(spec=spec)
    embedding_service = EmbeddingService(
        provider, spec=spec, text_preprocessor=preprocess_review_text
    )
    repository = PostgresVectorRepository()
    indexing_service = ReviewIndexingService(embedding_service, repository)
    return embedding_service, repository, indexing_service


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="Read-only plan (default). No provider calls, no writes.")
    mode.add_argument("--run", action="store_true",
                      help="Execute one bounded indexing window. Requires --limit.")
    parser.add_argument("--limit", type=int, default=None,
                        help="REQUIRED with --run: max canonical records to index.")
    parser.add_argument("--offset", type=int, default=0,
                        help="Corpus offset to resume from (default 0).")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Embed batch size (default: provider spec).")
    args = parser.parse_args(argv)

    embedding_service, repository, indexing_service = build_services()

    if not args.run:
        report = plan_canonical_index(
            canonical_catalog, repository, embedding_service, batch_size=args.batch_size
        )
        print("=== CANONICAL INDEX DRY-RUN (read-only) ===")
        print(f"canonical reviews : {report.total_canonical}")
        print(f"valid embeddings  : {report.valid_existing}")
        print(f"missing           : {report.missing}")
        print(f"stale rows/ids    : {report.stale_rows}/{report.stale_review_ids}")
        print(f"live canonical rows: {report.live_canonical_rows}")
        print(f"batches @ {report.batch_size}: {report.batches}")
        print(f"model/dimension   : {report.embedding_model}/{report.embedding_dimension}")
        if report.blockers:
            print("BLOCKERS:")
            for blocker in report.blockers:
                print(f"  - {blocker}")
            return 2
        print("No blockers. Re-run with --run --limit N to index one bounded window.")
        return 0

    if args.limit is None or args.limit <= 0:
        parser.error("--run requires an explicit positive --limit (no unbounded runs).")
    if args.offset < 0:
        parser.error("--offset must be >= 0.")

    report = run_canonical_index(
        canonical_catalog, repository, indexing_service,
        limit=args.limit, offset=args.offset,
    )
    print("=== CANONICAL INDEX RUN ===")
    print(f"attempted           : {report.attempted}")
    print(f"skipped (indexed)   : {report.skipped_already_indexed}")
    print(f"indexed             : {report.indexed}")
    print(f"updated             : {report.updated}")
    print(f"failed              : {report.failed} {list(report.failed_review_ids)}")
    print(f"invalid             : {report.invalid}")
    print(f"stale deleted       : {report.stale_deleted}")
    if report.blocked:
        print(f"BLOCKED: {report.block_reason}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
