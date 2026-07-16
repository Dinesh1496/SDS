"""
Health check endpoints.

Used by load balancers, Docker health checks, and monitoring systems.
No authentication required.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import check_db_connectivity
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime
    database: str


@router.get("", response_model=HealthResponse, summary="Platform health check")
def health_check() -> HealthResponse:
    """
    Return platform health status.

    Checks:
    - Application is running
    - Database is reachable

    Used by Docker HEALTHCHECK and load balancer probes.
    """
    db_ok = check_db_connectivity()

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc),
        database="ok" if db_ok else "unavailable",
    )


@router.get("/ready", summary="Readiness probe")
def readiness_probe() -> dict:
    """
    Kubernetes/Docker readiness probe.

    Returns 200 only when all dependencies are ready.
    """
    db_ok = check_db_connectivity()
    if not db_ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database not ready")
    return {"status": "ready"}


@router.get("/live", summary="Liveness probe")
def liveness_probe() -> dict:
    """
    Kubernetes/Docker liveness probe.

    Always returns 200 as long as the process is running.
    """
    return {"status": "alive"}
