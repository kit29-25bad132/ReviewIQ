import logging
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from models.dataset import EvaluationMetrics
from services.dataset_service import DatasetUnavailableError
from services.evaluation_service import evaluation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])

EvaluationSource = Literal["benchmark", "canonical"]


@router.get("", response_model=EvaluationMetrics | None, summary="Get cached evaluation metrics")
def get_evaluation(source: Optional[EvaluationSource] = Query(None, description="Evaluation source ('benchmark' or 'canonical'). Omitted means benchmark.")):
    return evaluation_service.metrics(source=source or "benchmark")


@router.post("/run", response_model=EvaluationMetrics, summary="Explicitly run AI evaluation")
def run_evaluation(limit: int | None = Query(None, ge=1, le=4915), reanalyze: bool = False, source: Optional[EvaluationSource] = Query(None, description="Evaluation source ('benchmark' or 'canonical'). Omitted means benchmark.")):
    try:
        return evaluation_service.run(limit=limit, reanalyze=reanalyze, source=source or "benchmark")
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
