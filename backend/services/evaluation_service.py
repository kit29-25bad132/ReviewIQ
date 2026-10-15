import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from models.dataset import EvaluationMetrics
from services.ai_analyzer import analyzer_service
from services.dataset_service import DatasetUnavailableError, dataset_service

EVALUATION_METHODOLOGY = "Actual sentiment is derived from ratings: 1–2 negative, 3 neutral, 4–5 positive. Reviews with rating_source 'not_found' (null predicted rating) are excluded from rating accuracy/MAE."

# Explicit evaluation sources. "benchmark" is the CSV-backed dataset with
# historical results; "canonical" is the Supabase-backed review corpus.
# Results are NEVER shared across sources, even when review IDs overlap.
BENCHMARK_SOURCE = "benchmark"
CANONICAL_SOURCE = "canonical"
SUPPORTED_SOURCES = (BENCHMARK_SOURCE, CANONICAL_SOURCE)

# Separator for canonical cache keys. Canonical review IDs (R00001…) never
# contain it, so namespaced keys can never collide with bare benchmark keys.
CANONICAL_KEY_SEPARATOR = "::"


def sanitize_version_tag(tag: Any) -> str:
    """Makes a dataset version safe for embedding in a cache key."""
    cleaned = str(tag or "").replace(":", "_").strip()
    return cleaned or "unknown"


def has_valid_prediction(entry: Any) -> bool:
    """A cached prediction is usable only with an in-range integer rating.

    Missing, null, or out-of-range predictions are treated as missing:
    excluded from accuracy/MAE denominators and re-analyzed on an
    authorized run. Deterministic for both sources.
    """
    if not isinstance(entry, dict):
        return False
    predicted = entry.get("predicted_rating")
    return isinstance(predicted, int) and 1 <= predicted <= 5


def compute_metrics(rows) -> EvaluationMetrics:
    matrix = [[0] * 5 for _ in range(5)]
    correct = sentiment_correct = rated = 0
    absolute_error = 0
    for row in rows:
        actual, predicted = row["actual_rating"], row["predicted_rating"]
        if isinstance(predicted, int) and 1 <= predicted <= 5:
            matrix[actual - 1][predicted - 1] += 1
            correct += actual == predicted
            absolute_error += abs(actual - predicted)
            rated += 1
        sentiment_correct += row["actual_sentiment"] == row["predicted_sentiment"]
    total = len(rows)
    rated_total = rated or 1
    return EvaluationMetrics(evaluated_reviews=total, rating_accuracy=round(correct / rated_total, 4), rating_mae=round(absolute_error / rated_total, 4), sentiment_accuracy=round(sentiment_correct / total, 4) if total else 0.0, confusion_matrix=matrix, methodology=EVALUATION_METHODOLOGY)


class EvaluationService:
    """Source-separated evaluation with versioned, collision-free results.

    Persistence stays a single JSON object (`results.json`) for backward
    compatibility:
    - benchmark results keep bare review-ID keys (historical shape; extra
      `source`/`dataset_version` metadata is additive).
    - canonical results use `canonical::<version>::<review_id>` keys and can
      never collide with benchmark entries, even for identical review IDs.
    - legacy entries without metadata are interpreted as benchmark results
      with an unknown benchmark version (documented compatibility rule);
      they are never returned as canonical results.
    - benchmark metrics aggregate all bare-key entries (legacy semantics,
      version-agnostic, so historical results keep working).
    - canonical metrics aggregate only entries for the CURRENT canonical
      dataset version; entries from other versions are ignored, never reused.
    """

    def __init__(self) -> None:
        self.path = Path(__file__).resolve().parent.parent / "evaluation_results" / "results.json"
        self._lock = Lock()

    def _cache(self):
        if not self.path.exists(): return {}
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError): return {}

    def _save(self, cache):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    @staticmethod
    def _normalize_source(source: Optional[str]) -> str:
        normalized = (source or BENCHMARK_SOURCE).strip().lower()
        if normalized not in SUPPORTED_SOURCES:
            raise ValueError(f"Unsupported evaluation source: {source!r}. Supported: {list(SUPPORTED_SOURCES)}")
        return normalized

    @staticmethod
    def _benchmark_version() -> str:
        """Content version of the CSV benchmark file (sha prefix)."""
        try:
            digest = hashlib.sha256(dataset_service.path.read_bytes()).hexdigest()[:12]
            return f"csv-{digest}"
        except (OSError, TypeError, ValueError):
            # TypeError covers whole-module test doubles without a real path.
            return "csv-unknown"

    @staticmethod
    def _canonical_version() -> str:
        """Currently active canonical dataset version tag."""
        try:
            from services.catalog.catalog_service import canonical_catalog
            return sanitize_version_tag(canonical_catalog.get_dataset_version())
        except Exception:
            return "canonical-unknown"

    @staticmethod
    def _cache_key(source: str, version: str, review_id: str) -> str:
        if source == BENCHMARK_SOURCE:
            return str(review_id)
        return f"{CANONICAL_SOURCE}{CANONICAL_KEY_SEPARATOR}{sanitize_version_tag(version)}{CANONICAL_KEY_SEPARATOR}{review_id}"

    @staticmethod
    def _benchmark_records():
        return dataset_service.records()

    @staticmethod
    def _canonical_records(limit: Optional[int] = None):
        from services.catalog.catalog_service import canonical_catalog
        if not canonical_catalog.is_configured():
            raise DatasetUnavailableError(
                "Canonical product catalog is not configured. Set DATABASE_URL for canonical evaluation."
            )
        rows, _ = canonical_catalog.query_dataset_reviews(limit or 5000, 0, None, None, None, None)
        records = []
        for r in rows[:limit] if limit else rows:
            records.append(SimpleNamespace(
                id=r["id"],
                review_text=r["review_text"],
                actual_rating=r["actual_rating"],
                actual_sentiment=r["actual_sentiment"],
            ))
        return records

    def _rows_for_source(self, source: str, cache: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Builds metric rows for one source from cache entries only.

        No provider calls, no database reads. Missing predictions stay
        missing: only present entries become rows, and compute_metrics
        excludes invalid predictions from accuracy/MAE denominators.
        """
        rows = []
        if source == BENCHMARK_SOURCE:
            for key, entry in cache.items():
                if CANONICAL_KEY_SEPARATOR in key or not isinstance(entry, dict):
                    continue
                rows.append({
                    "actual_rating": entry.get("actual_rating"),
                    "predicted_rating": entry.get("predicted_rating"),
                    "actual_sentiment": entry.get("actual_sentiment"),
                    "predicted_sentiment": entry.get("predicted_sentiment"),
                })
            return rows
        version = self._canonical_version()
        prefix = f"{CANONICAL_SOURCE}{CANONICAL_KEY_SEPARATOR}{version}{CANONICAL_KEY_SEPARATOR}"
        for key, entry in cache.items():
            if not key.startswith(prefix) or not isinstance(entry, dict):
                continue
            rows.append({
                "actual_rating": entry.get("actual_rating"),
                "predicted_rating": entry.get("predicted_rating"),
                "actual_sentiment": entry.get("actual_sentiment"),
                "predicted_sentiment": entry.get("predicted_sentiment"),
            })
        return rows

    def metrics(self, source: Optional[str] = None):
        """Computes metrics from cached predictions only. Zero provider calls.

        Returns None when no usable rows exist for the source (benchmark:
        empty cache; canonical: database unconfigured or no entries for the
        current dataset version).
        """
        normalized = self._normalize_source(source)
        if normalized == CANONICAL_SOURCE:
            try:
                from services.catalog.catalog_service import canonical_catalog
                if not canonical_catalog.is_configured():
                    return None
            except Exception:
                return None
        cache = self._cache()
        rows = self._rows_for_source(normalized, cache)
        if not rows:
            return None
        return compute_metrics(rows)

    def run(self, limit: int | None = None, reanalyze: bool = False, source: Optional[str] = None):
        """Explicitly evaluates records, analyzing ONLY records that lack a
        valid cached prediction (or all in-scope records when reanalyze=True).

        A fully cached rerun performs zero provider calls. New predictions
        are namespaced by (source, dataset version) so benchmark and
        canonical results — and results across dataset versions — can never
        contaminate each other. Historical benchmark entries are preserved
        untouched (rewritten only if re-analyzed, keeping their bare keys).
        """
        normalized = self._normalize_source(source)
        if not analyzer_service.is_configured():
            raise ValueError("AI analysis is temporarily unavailable.")
        if normalized == BENCHMARK_SOURCE:
            records = self._benchmark_records()[:limit] if limit else self._benchmark_records()
            version = self._benchmark_version()
        else:
            records = self._canonical_records(limit)
            version = self._canonical_version()
        with self._lock:
            cache = self._cache()
            for record in records:
                key = self._cache_key(normalized, version, record.id)
                existing = cache.get(key)
                if existing is not None and has_valid_prediction(existing) and not reanalyze:
                    continue
                ai = analyzer_service.analyze_review(record.review_text)
                cache[key] = {
                    "actual_rating": record.actual_rating,
                    "predicted_rating": ai.rating,
                    "predicted_rating_source": ai.rating_source,
                    "actual_sentiment": record.actual_sentiment,
                    "predicted_sentiment": ai.sentiment,
                    "pros": [p.model_dump() for p in ai.pros],
                    "cons": [c.model_dump() for c in ai.cons],
                    "summary": ai.summary,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": normalized,
                    "dataset_version": version,
                }
            self._save(cache)
        return self.metrics(source=normalized)


evaluation_service = EvaluationService()
