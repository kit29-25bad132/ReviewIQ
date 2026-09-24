from fastapi import APIRouter, HTTPException, Query
from models.dataset import EvaluationMetrics
from services.dataset_service import DatasetUnavailableError
from services.evaluation_service import evaluation_service

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


@router.get("", response_model=EvaluationMetrics | None, summary="Get cached evaluation metrics")
def get_evaluation():
    return evaluation_service.metrics()


@router.post("/run", response_model=EvaluationMetrics, summary="Explicitly run cached Gemini evaluation")
def run_evaluation(limit: int | None = Query(None, ge=1, le=4915), reanalyze: bool = False):
    try:
        return evaluation_service.run(limit=limit, reanalyze=reanalyze)
    except DatasetUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
