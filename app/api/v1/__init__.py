"""API v1 router registration."""

from fastapi import APIRouter

from app.api.v1.endpoints import clusters, health, metrics

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(clusters.router, prefix="/clusters", tags=["Clusters"])
api_router.include_router(metrics.router, tags=["Metrics"])
