import logging

from fastapi import APIRouter, HTTPException, status

from models.retrieval import (
    RetrievalStatusResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResultItem,
)
from services.embeddings.errors import EmbeddingError, EmbeddingErrorType
from services.retrieval.runtime import build_search_service, retrieval_status
from services.retrieval.vector_repository import ReviewSearchFilters

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["V2 Retrieval"])

# Normalized error categories -> (HTTP status, fixed user-safe message). Raw
# provider/database internals are logged server-side only, never returned.
_STATUS_BY_ERROR = {
    EmbeddingErrorType.INVALID_INPUT: status.HTTP_400_BAD_REQUEST,
    EmbeddingErrorType.CONFIGURATION: status.HTTP_503_SERVICE_UNAVAILABLE,
    EmbeddingErrorType.AUTHENTICATION: status.HTTP_503_SERVICE_UNAVAILABLE,
    EmbeddingErrorType.DATABASE_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
    EmbeddingErrorType.RATE_LIMIT: status.HTTP_429_TOO_MANY_REQUESTS,
    EmbeddingErrorType.TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    EmbeddingErrorType.TRANSIENT: status.HTTP_502_BAD_GATEWAY,
}
_MESSAGE_BY_ERROR = {
    EmbeddingErrorType.INVALID_INPUT: "Invalid semantic search request.",
    EmbeddingErrorType.CONFIGURATION: "Semantic retrieval is not configured on the server.",
    EmbeddingErrorType.AUTHENTICATION: "Embedding provider authentication failed.",
    EmbeddingErrorType.DATABASE_ERROR: "Semantic retrieval store is temporarily unavailable.",
    EmbeddingErrorType.RATE_LIMIT: "Embedding rate limit reached. Please try again shortly.",
    EmbeddingErrorType.TIMEOUT: "Embedding provider timed out. Please try again.",
    EmbeddingErrorType.TRANSIENT: "Embedding provider is temporarily unavailable.",
}
_DEFAULT_MESSAGE = "Semantic retrieval failed. Please try again."


@router.get(
    "/retrieval/status",
    response_model=RetrievalStatusResponse,
    summary="V2 retrieval configuration status (non-secret)",
)
def get_retrieval_status() -> RetrievalStatusResponse:
    return RetrievalStatusResponse(**retrieval_status())


@router.post(
    "/retrieval/search",
    response_model=SemanticSearchResponse,
    summary="Semantic similarity search over stored review embeddings",
    description=(
        "V2 retrieval foundation: embeds the query and returns the most similar "
        "stored reviews using cosine similarity. No LLM generation is involved."
    ),
)
def semantic_search(payload: SemanticSearchRequest) -> SemanticSearchResponse:
    filters = ReviewSearchFilters(
        product_id=payload.product_id,
        min_rating=payload.min_rating,
        max_rating=payload.max_rating,
        source=payload.source,
        review_date_from=payload.review_date_from,
        review_date_to=payload.review_date_to,
    )
    if filters.is_empty():
        filters = None

    try:
        outcome = build_search_service().search(
            payload.query,
            top_k=payload.top_k,
            similarity_threshold=payload.similarity_threshold,
            filters=filters,
        )
    except EmbeddingError as exc:
        logger.warning(
            "Semantic search failed (%s): %s", exc.error_type.value, exc, exc_info=True
        )
        raise HTTPException(
            status_code=_STATUS_BY_ERROR.get(
                exc.error_type, status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=_MESSAGE_BY_ERROR.get(exc.error_type, _DEFAULT_MESSAGE),
        )

    return SemanticSearchResponse(
        success=True,
        query=outcome.query_text,
        top_k=outcome.top_k,
        similarity_threshold=outcome.similarity_threshold,
        embedding_model=outcome.embedding_model,
        embedding_dimension=outcome.embedding_dimension,
        result_count=len(outcome.results),
        results=[
            SemanticSearchResultItem(
                review_id=result.review_id,
                product_id=result.product_id,
                review_text=result.review_text,
                similarity=result.similarity,
                distance=result.distance,
                rating=result.rating,
                source=result.source,
                embedding_model=result.embedding_model,
            )
            for result in outcome.results
        ],
        error=None,
    )
