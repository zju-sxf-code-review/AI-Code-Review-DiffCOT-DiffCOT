"""
DiffCOT Code Review Backend

FastAPI application for AI-powered code review.
"""

from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import github_router, review_router, settings_router, conversations_router, semgrep_rules_router
from api.models.schemas import HealthResponse
from utils.logger import get_logger

logger = get_logger(__name__)

# Application version
VERSION = "1.0.0"

# Create FastAPI application
app = FastAPI(
    title="DiffCOT Code Review API",
    description="AI-powered code review for GitHub Pull Requests",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(github_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(semgrep_rules_router, prefix="/api")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=VERSION,
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "DiffCOT Code Review API",
        "version": VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(f"Starting DiffCOT Code Review API v{VERSION}")
    logger.info("API documentation available at /docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down DiffCOT Code Review API")


if __name__ == "__main__":
    import uvicorn
    from utils.paths import is_packaged

    if is_packaged():
        # 打包后：直接传递 app 对象，禁用 reload
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8765,
            reload=False,
            log_level="info"
        )
    else:
        # 开发模式：使用字符串形式支持 reload
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=8765,
            reload=True,
            log_level="info"
        )
