import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .routers import tasks_router
from .database import init_db, get_engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Evolution of Todo API",
    description="REST API for the Evolution of Todo project (Phase 2.2)",
    version="0.1.0"
)

# Configure CORS for frontend communication
# Phase 2.4: Frontend Integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
        "https://todo-evolution-liart.vercel.app",  # Vercel frontend production
        "https://todo-evolution.vercel.app",  # Vercel alias (if available)
        "https://evaluation-todo.vercel.app",  # Backend itself (for health checks)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Request logging middleware for debugging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests for debugging."""
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {request.method} {request.url.path} → {response.status_code}")
    return response


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on application startup."""
    logger.info("=" * 60)
    logger.info("Starting database initialization...")

    try:
        # Test database connection
        engine = get_engine()
        logger.info(f"✓ Database engine created: {engine.url.database}")

        # Initialize tables
        init_db()
        logger.info("✓ Database tables initialized successfully")

        # Verify connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("✓ Database connection verified")

        logger.info("=" * 60)
        logger.info("Database initialization complete!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"✗ Database initialization FAILED: {str(e)}")
        logger.error("=" * 60)
        raise


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Global handler for database errors."""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "A database error occurred. Please try again later."
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Global handler for unexpected errors."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred."
            }
        },
    )


app.include_router(tasks_router)


@app.get("/", tags=["system"])
async def root():
    """API root endpoint with service information."""
    return {
        "service": "Evolution of Todo API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["system"])
async def health_check():
    """System health check endpoint."""
    return {"status": "ok"}


@app.get("/api/ping", tags=["system"])
async def ping():
    """
    Simple ping endpoint for frontend connectivity testing.
    No authentication required.
    """
    return {"ping": "pong", "cors": "enabled"}
