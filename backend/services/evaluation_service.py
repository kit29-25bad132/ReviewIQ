import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from models.dataset import EvaluationMetrics
from services.ai_analyzer import analyzer_service
from services.dataset_service import dataset_service


class EvaluationService:
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

    def metrics(self):
        cache = self._cache()
        if not cache: return None
        rows = list(cache.values())
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
        return EvaluationMetrics(evaluated_reviews=total, rating_accuracy=round(correct / rated_total, 4), rating_mae=round(absolute_error / rated_total, 4), sentiment_accuracy=round(sentiment_correct / total, 4), confusion_matrix=matrix, methodology="Actual sentiment is derived from ratings: 1–2 negative, 3 neutral, 4–5 positive. Reviews with rating_source 'not_found' (null predicted rating) are excluded from rating accuracy/MAE.")

    def run(self, limit: int | None = None, reanalyze: bool = False):
        if not analyzer_service.is_configured():
            raise ValueError("AI analysis is temporarily unavailable.")
        records = dataset_service.records()[:limit] if limit else dataset_service.records()
        with self._lock:
            cache = self._cache()
            for record in records:
                if record.id in cache and not reanalyze: continue
                ai = analyzer_service.analyze_review(record.review_text)
                cache[record.id] = {"actual_rating": record.actual_rating, "predicted_rating": ai.rating, "predicted_rating_source": ai.rating_source, "actual_sentiment": record.actual_sentiment, "predicted_sentiment": ai.sentiment, "pros": [p.model_dump() for p in ai.pros], "cons": [c.model_dump() for c in ai.cons], "summary": ai.summary, "timestamp": datetime.now(timezone.utc).isoformat()}
            self._save(cache)
        return self.metrics()


evaluation_service = EvaluationService()
