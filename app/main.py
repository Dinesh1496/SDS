"""
SDS Nexus Storage Operations & Chargeback Platform.

Application entry point — FastAPI app factory with:
- CORS middleware
- Request ID middleware
- Exception handlers
- API router registration
- Startup / shutdown lifecycle hooks
- OpenAPI documentation customisation
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import set_app_info
from app.db.session import check_db_connectivity
import sys

# ---------------------------------------------------------------------------
# Initialise logging before anything else
# ---------------------------------------------------------------------------

settings = get_settings()
log_cfg = settings.get_logging_settings()

configure_logging(
    level=log_cfg.level,
    log_format=log_cfg.format,
    output_path=log_cfg.output_path if settings.is_production else None,
    rotation=log_cfg.rotation,
    retention=log_cfg.retention,
    backtrace=log_cfg.backtrace,
    diagnose=log_cfg.diagnose,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown events.

    Startup:
    - Verify database connectivity
    - Log configuration summary

    Shutdown:
    - Flush any pending log records
    """
    logger.info(
        "Starting SDS Nexus Platform",
        version=settings.app_version,
        environment=settings.app_env,
    )
    
    # Initialize Prometheus metrics with app info
    set_app_info(
        version=settings.app_version,
        environment=settings.app_env,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )

    # Verify DB on startup
    if not check_db_connectivity():
        logger.error("Database is unreachable at startup — check DB_HOST, DB_PORT, DB_NAME")
    else:
        logger.info("Database connectivity confirmed")

    logger.info(
        "Platform ready",
        host=settings.app_host,
        port=settings.app_port,
        docs_url="/docs",
    )

    yield

    logger.info("Platform shutting down")


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """
    Construct and configure the FastAPI application instance.

    Returns a fully configured app ready to be served by Uvicorn.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Enterprise Storage Operations & Chargeback Platform for "
            "Ceph SDS (Software-Defined Storage) environments."
        ),
        contact={
            "name": "Storage Operations Team",
        },
        license_info={"name": "Proprietary — Internal Use Only"},
        openapi_url="/openapi.json" if not settings.is_production else None,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app_cors_origins.split(",") if hasattr(settings, "app_cors_origins") else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Request ID & timing middleware
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        """Attach a unique request ID and log request timing."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.monotonic()

        response = await call_next(request)

        duration_ms = (time.monotonic() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        logger.info(
            "HTTP request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
        )
        return response

    # ------------------------------------------------------------------
    # Global exception handlers
    # ------------------------------------------------------------------
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("Validation error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception(
            "Unhandled exception",
            path=request.url.path,
            request_id=request_id,
            error=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred. Please contact the operations team.",
                "request_id": request_id,
            },
        )

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(api_router, prefix="/api/v1")

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (used by Uvicorn)
# ---------------------------------------------------------------------------
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_development,
        log_level=log_cfg.level.lower(),
        access_log=False,   # Handled by our middleware
    )
