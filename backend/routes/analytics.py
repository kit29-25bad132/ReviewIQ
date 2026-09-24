from collections import defaultdict
from fastapi import APIRouter, HTTPException, Query
from models.dataset import OverviewAnalytics, ProductAnalytics
from services.dataset_service import DatasetUnavailableError, dataset_service
from services.evaluation_service import evaluation_service

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/overview", response_model=OverviewAnalytics)
def overview():
    try:
        rows = dataset_service.records()
        counts = {"positive": 0, "neutral": 0, "negative": 0}
        rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for row in rows:
            counts[row.actual_sentiment] += 1
            if 1 <= row.actual_rating <= 5:
                rating_dist[row.actual_rating] += 1

        avg_rating = round(sum(r.actual_rating for r in rows) / len(rows), 2) if rows else 0.0
        return OverviewAnalytics(
            total_reviews=len(rows),
            average_rating=avg_rating,
            positive_reviews=counts["positive"],
            neutral_reviews=counts["neutral"],
            negative_reviews=counts["negative"],
            rating_distribution=rating_dist,
        )
    except DatasetUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/products", response_model=list[ProductAnalytics])
def products(limit: int = Query(100, ge=1, le=500)):
    try:
        groups = defaultdict(list)
        for row in dataset_service.records(): groups[row.asin].append(row)
        cache = evaluation_service._cache()
        result = []
        for asin, rows in groups.items():
            predictions = [cache[r.id]["predicted_rating"] for r in rows if r.id in cache]
            result.append(ProductAnalytics(asin=asin, product_name=None, review_count=len(rows), average_actual_rating=round(sum(r.actual_rating for r in rows)/len(rows), 2), average_ai_rating=round(sum(predictions)/len(predictions), 2) if predictions else None, positive_reviews=sum(r.actual_sentiment == "positive" for r in rows), neutral_reviews=sum(r.actual_sentiment == "neutral" for r in rows), negative_reviews=sum(r.actual_sentiment == "negative" for r in rows), helpful_votes=sum(r.helpful_yes or 0 for r in rows)))
        return sorted(result, key=lambda item: item.review_count, reverse=True)[:limit]
    except DatasetUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
