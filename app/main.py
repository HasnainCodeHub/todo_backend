import asyncio
import logging
from typing import Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .routers import tasks_router, chat_router
from .database import init_db, get_engine
from .crud.task import create_task, get_tasks, update_task, delete_task, toggle_complete, get_task
from .mcp_server import get_mcp_app
from .middleware.mcp_auth_middleware import MCPAuthMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP server instance (initialized in lifespan)
_mcp_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global _mcp_app

    # Startup
    logger.info("=" * 60)
    logger.info("Starting database initialization...")

    try:
        # Test database connection
        engine = get_engine()
        logger.info(f"[OK] Database engine created: {engine.url.database}")

        # Initialize tables
        init_db()
        logger.info("[OK] Database tables initialized successfully")

        # Verify connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("[OK] Database connection verified")

        logger.info("=" * 60)
        logger.info("Database initialization complete!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"[FAIL] Database initialization FAILED: {str(e)}")
        logger.error("=" * 60)
        raise

    # Initialize MCP server
    try:
        from .tools.task_tools import mcp_app
        _mcp_app = mcp_app
        logger.info("[OK] MCP server initialized")
    except ImportError as e:
        logger.warning(f"MCP server not available: {e}")

    # Manually trigger the FastMCP sub-app's ASGI lifespan.
    # Starlette does NOT automatically forward lifespan events to mounted
    # sub-apps, so the StreamableHTTPSessionManager task group would never
    # be initialised without this explicit start.
    startup_done = asyncio.Event()
    shutdown_signal = asyncio.Event()

    async def _mcp_receive():
        if not startup_done.is_set():
            return {"type": "lifespan.startup"}
        await shutdown_signal.wait()
        return {"type": "lifespan.shutdown"}

    async def _mcp_send(message: dict):
        if message["type"] == "lifespan.startup.complete":
            startup_done.set()

    mcp_lifespan_task = asyncio.create_task(
        mcp_http_app(
            {"type": "lifespan", "asgi": {"version": "3.0", "spec_version": "2.0"}, "state": {}},
            _mcp_receive,
            _mcp_send,
        )
    )

    try:
        await asyncio.wait_for(startup_done.wait(), timeout=10.0)
        logger.info("[OK] FastMCP session manager started")
    except asyncio.TimeoutError:
        logger.error("[FAIL] FastMCP session manager startup timed out")
        raise RuntimeError("FastMCP session manager failed to start within 10s")

    yield

    # Shutdown: signal the MCP lifespan task and wait for clean exit
    shutdown_signal.set()
    try:
        await asyncio.wait_for(mcp_lifespan_task, timeout=5.0)
    except (asyncio.TimeoutError, Exception):
        logger.warning("MCP lifespan task did not shut down cleanly")

    logger.info("Application shutting down...")


# Create FastAPI application with lifespan
app = FastAPI(
    title="Evolution of Todo API",
    description="REST API for the Evolution of Todo project (Phase 2.2)",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS for frontend communication
# Phase 2.4: Frontend Integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",          # Next.js dev server (default)
        "http://127.0.0.1:3000",          # Next.js dev server (alt)
        "https://ai-based-todo.vercel.app",  # Production FRONTEND
        "https://*.vercel.app",            # Vercel preview deployments
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
app.include_router(chat_router)


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


# MCP Server: mounted as a catch-all AFTER all explicit API routes.
# Requests to /mcp are NOT matched by any API route and fall through to this mount.
# MCPAuthMiddleware validates JWT and populates current_user_var for MCP tools.
# The chat_orchestrator agent connects via MCPServerStreamableHttp to this endpoint.
mcp_http_app = get_mcp_app()  # FastMCP streamable HTTP ASGI app
app.mount("/", MCPAuthMiddleware(app=mcp_http_app))
