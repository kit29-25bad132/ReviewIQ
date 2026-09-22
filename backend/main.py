import os
import logging
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes.review import router as review_router
from services.ai_analyzer import analyzer_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("product_review_analyzer")

app = FastAPI(
    title="Product Review Analyzer API",
    description="Production-ready AI backend for structured customer review analysis",
    version="1.0.0",
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

# Include routers
app.include_router(review_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint returning service and AI provider status.
    Guarantees zero leakage of API secrets.
    """
    return {
        "status": "ok",
        "service": "Product Review Analyzer Backend",
        "version": "1.0.0",
        "ai_provider": "Google Gemini",
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
