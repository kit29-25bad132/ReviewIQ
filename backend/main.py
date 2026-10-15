import os
import logging
import uuid
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes.review import router as review_router
from routes.dataset import router as dataset_router
from routes.analytics import router as analytics_router
from routes.evaluation import router as evaluation_router
from routes.products import router as products_router
from routes.reviews import router as reviews_router
from routes.retrieval import router as retrieval_router
from services.ai_analyzer import analyzer_service
from services.ai.registry import GEMINI_PROVIDER, GROQ_PROVIDER, OPENROUTER_PROVIDER
from services.observability import RequestIdFilter, request_id_var

# Setup logging (V2-P11: every line carries the request correlation ID).
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s [rid=%(request_id)s]: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
)
# The filter defaults missing IDs to "-", so records logged outside any
# request (startup, background) still format safely.
for _handler in logging.getLogger().handlers:
    if not any(isinstance(f, RequestIdFilter) for f in _handler.filters):
        _handler.addFilter(RequestIdFilter())
logger = logging.getLogger("product_review_analyzer")

# Single source of truth for the API version (Gate 2): used both by the
# FastAPI app and the /health response so they can never drift.
APP_VERSION = "2.0.0"

app = FastAPI(
    title="ReviewIQ - Product Review Intelligence API",
    description="Production-ready AI backend for dataset-based product search, review analytics, and ground-truth intelligence",
    version=APP_VERSION,
)

# CORS Configuration
default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000,http://127.0.0.1:3000"
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", default_origins)
origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestCorrelationMiddleware:
    """Pure-ASGI middleware assigning one correlation ID per HTTP request.

    V2-P11: sets ``request_id_var`` to a ``uuid4().hex`` for the duration of
    the request and resets it in ``finally`` (async/await-safe: the ContextVar
    is set and reset inside the request task's context, so concurrent
    requests never see each other's IDs). The ID appears only in server log
    lines — never in the response body or headers (no ``X-Request-ID``).
    Non-HTTP scopes (lifespan) pass through untouched.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        token = request_id_var.set(uuid.uuid4().hex)
        try:
            await self.app(scope, receive, send)
        finally:
            request_id_var.reset(token)


app.add_middleware(RequestCorrelationMiddleware)

# Include routers
app.include_router(products_router)
app.include_router(reviews_router)
app.include_router(review_router)
app.include_router(dataset_router)
app.include_router(analytics_router)
app.include_router(evaluation_router)
app.include_router(retrieval_router)


# Provider name -> env var carrying its API key. Gate 2 (Phase 4): /health
# reports only what is actually configured — never a hardcoded provider claim.
_PROVIDER_ENV_KEYS = (
    (GEMINI_PROVIDER, "GEMINI_API_KEY"),
    (GROQ_PROVIDER, "GROQ_API_KEY"),
    (OPENROUTER_PROVIDER, "OPENROUTER_API_KEY"),
)


def configured_ai_provider_label() -> str:
    """Comma-separated list of configured AI providers (empty when none).

    Truthful by construction: derived from which provider API keys are
    actually present in the environment, not from a hardcoded label. Keys
    themselves are never exposed — only provider names.
    """
    configured = [
        name
        for name, env_var in _PROVIDER_ENV_KEYS
        if (os.getenv(env_var) or "").strip()
    ]
    return ", ".join(configured)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint returning service and AI configuration status.
    Guarantees zero leakage of API secrets.
    """
    return {
        "status": "ok",
        "service": "Product Review Analyzer Backend",
        "version": APP_VERSION,
        "ai_provider": configured_ai_provider_label(),
        "ai_configured": analyzer_service.is_configured(),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Fallback handler to prevent unhandled stack trace exposure."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": "An unexpected internal server error occurred."
        }
    )


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting server on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
