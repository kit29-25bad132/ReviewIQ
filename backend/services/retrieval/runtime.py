"""Production wiring for the retrieval layer.

Builds the embedding service (Gemini adapter + registry spec) and the
Postgres/pgvector repository. Construction is cheap and lazy: no database
connection or provider call happens until a request actually runs, and the API
key / DSN are resolved at call time.
"""

from services.embeddings.providers.gemini import GeminiEmbeddingProvider
from services.embeddings.registry import resolve_embedding_model_spec
from services.embeddings.service import EmbeddingService
from services.retrieval.indexing_service import ReviewIndexingService
from services.retrieval.postgres_vector_repository import PostgresVectorRepository
from services.retrieval.database import PostgresDatabase
from services.retrieval.preprocessing import preprocess_review_text
from services.retrieval.search_service import SemanticSearchService
from services.retrieval.vector_repository import VectorRepository


def build_embedding_service() -> EmbeddingService:
    spec = resolve_embedding_model_spec()
    provider = GeminiEmbeddingProvider(spec=spec)
    return EmbeddingService(
        provider, spec=spec, text_preprocessor=preprocess_review_text
    )


def build_vector_repository() -> VectorRepository:
    return PostgresVectorRepository()


def build_indexing_service() -> ReviewIndexingService:
    return ReviewIndexingService(build_embedding_service(), build_vector_repository())


def build_search_service() -> SemanticSearchService:
    return SemanticSearchService(build_embedding_service(), build_vector_repository())


def retrieval_status() -> dict:
    """Non-secret configuration status for diagnostics/manual verification."""
    spec = resolve_embedding_model_spec()
    provider = GeminiEmbeddingProvider(spec=spec)
    database = PostgresDatabase()
    return {
        "embedding_provider": spec.provider,
        "embedding_model": spec.model,
        "embedding_dimension": spec.dimension,
        "embeddings_configured": provider.is_configured(),
        "database_configured": database.is_configured(),
        "similarity_metric": "cosine",
    }
