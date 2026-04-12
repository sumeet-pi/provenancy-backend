"""
Provenancy API - Main Application Entry Point

A production-ready FastAPI backend server connected to PostgreSQL (Supabase).
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.schemas import HealthResponse
from app.auth import router as auth_router
from app.routes.student import router as student_router
from app.routes.supervisor import router as supervisor_router
from app.routes.skills import router as skills_router
from app.routes.engagements import router as engagements_router

from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("Initializing database connection...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready FastAPI backend for Provenancy project",
    lifespan=lifespan,
)

# ============== CORS Middleware ==============
# Configure CORS to allow frontend to communicate with backend
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Global Exception Handlers ==============

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle validation errors with a clean structured response.
    """
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({
            "field": field,
            "message": error["msg"]
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Catch all unhandled exceptions and return a generic error response.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


# ============== Health Check Endpoint ==============
@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """
    Health check endpoint to verify API and database connectivity.

    Returns:
        Health status including API version and database status
    """
    from app.database import engine

    # Check database connectivity
    db_status = "healthy"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    return HealthResponse(
        status="ok" if db_status == "healthy" else "degraded",
        database=db_status,
        version=settings.APP_VERSION
    )


# ============== Include Routers ==============
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(supervisor_router)
app.include_router(skills_router)
app.include_router(engagements_router)


# ============== Root Endpoint ==============
@app.get("/", tags=["Root"])
def root() -> dict:
    """Root endpoint returning API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False  # False in production
    )
