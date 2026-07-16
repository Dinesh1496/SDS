"""
Prometheus metrics endpoint.

Exposes metrics in Prometheus format for scraping.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.metrics import metrics_response

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def get_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus exposition format for scraping by
    Prometheus server.
    
    This endpoint is excluded from OpenAPI documentation and does not
    require authentication to allow Prometheus to scrape it.
    """
    return metrics_response()
