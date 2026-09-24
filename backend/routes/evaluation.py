import logging
from fastapi import APIRouter, HTTPException, Query
from models.dataset import EvaluationMetrics
from services.dataset_service import DatasetUnavailableError
from services.evaluation_service import evaluation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


@router.get("", response_model=EvaluationMetrics | None, summary="Get cached evaluation metrics")
def get_evaluation():
    return evaluation_service.metrics()


@router.post("/run", response_model=EvaluationMetrics, summary="Explicitly run cached Gemini evaluation")
def run_evaluation(limit: int | None = Query(None, ge=1, le=4915), reanalyze: bool = False):
    try:
        return evaluation_service.run(limit=limit, reanalyze=reanalyze)
    except DatasetUnavailableError as exc:
        logger.warning("Evaluation dataset unavailable: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Evaluation dataset is currently unavailable. Please try again later.",
        )
    except ValueError as exc:
        logger.warning("Evaluation service error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Evaluation service is temporarily unavailable. Please try again later.",
        )
    except Exception as exc:
        logger.error("Unexpected evaluation error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Evaluation service is temporarily unavailable. Please try again later.",
        )
