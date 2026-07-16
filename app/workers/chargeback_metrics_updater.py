"""
Chargeback metrics updater worker.

Periodically updates Prometheus metrics for tenant usage and costs.
Should run after RGW data collection to ensure metrics are up-to-date.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import (
    chargeback_monthly_cost_gbp,
    chargeback_monthly_cost_usd,
    chargeback_tenant_usage_bytes,
    worker_job_execution_total,
    worker_job_duration_seconds,
    worker_job_last_success_timestamp,
)
from app.db.session import get_db

if TYPE_CHECKING:
    from app.models.cluster import Cluster
    from app.models.storage import Bucket

logger = get_logger(__name__)


def calculate_monthly_cost(
    usage_bytes: int,
    gbp_per_gb_month: float = 0.05,
    usd_per_gb_month: float = 0.06,
) -> tuple[float, float]:
    """
    Calculate monthly cost for storage usage.
    
    Args:
        usage_bytes: Storage usage in bytes
        gbp_per_gb_month: Cost per GB per month in GBP
        usd_per_gb_month: Cost per GB per month in USD
    
    Returns:
        Tuple of (cost_gbp, cost_usd)
    """
    usage_gb = usage_bytes / (1024 ** 3)
    cost_gbp = usage_gb * gbp_per_gb_month
    cost_usd = usage_gb * usd_per_gb_month
    return cost_gbp, cost_usd


def update_chargeback_metrics(db: Session) -> None:
    """
    Update Prometheus chargeback metrics from database.
    
    Reads bucket usage data from database and updates Prometheus metrics
    for tenant usage and costs.
    """
    from app.models.cluster import Cluster
    from app.models.storage import Bucket
    
    start_time = datetime.utcnow()
    
    try:
        logger.info("Starting chargeback metrics update")
        
        # Get all clusters
        clusters = db.execute(select(Cluster)).scalars().all()
        
        for cluster in clusters:
            logger.debug(f"Processing cluster {cluster.name}")
            
            # Get tenant usage by summing bucket sizes per tenant
            tenant_usage_query = (
                select(
                    Bucket.tenant,
                    func.sum(Bucket.size_bytes).label("total_bytes"),
                )
                .where(Bucket.cluster_id == cluster.id)
                .group_by(Bucket.tenant)
            )
            
            tenant_usage_results = db.execute(tenant_usage_query).all()
            
            # Update metrics for each tenant
            for tenant, total_bytes in tenant_usage_results:
                if tenant is None or total_bytes is None:
                    continue
                
                # Update usage metric
                chargeback_tenant_usage_bytes.labels(
                    cluster_name=cluster.name,
                    tenant=tenant,
                ).set(total_bytes)
                
                # Calculate and update cost metrics
                cost_gbp, cost_usd = calculate_monthly_cost(total_bytes)
                
                chargeback_monthly_cost_gbp.labels(
                    cluster_name=cluster.name,
                    tenant=tenant,
                ).set(cost_gbp)
                
                chargeback_monthly_cost_usd.labels(
                    cluster_name=cluster.name,
                    tenant=tenant,
                ).set(cost_usd)
                
                logger.debug(
                    f"Updated metrics for tenant {tenant}",
                    cluster=cluster.name,
                    usage_gb=round(total_bytes / (1024**3), 2),
                    cost_gbp=round(cost_gbp, 2),
                    cost_usd=round(cost_usd, 2),
                )
        
        # Record successful execution
        duration = (datetime.utcnow() - start_time).total_seconds()
        worker_job_execution_total.labels(
            job_name="chargeback_metrics_updater",
            status="success",
        ).inc()
        worker_job_duration_seconds.labels(
            job_name="chargeback_metrics_updater",
        ).observe(duration)
        worker_job_last_success_timestamp.labels(
            job_name="chargeback_metrics_updater",
        ).set(datetime.utcnow().timestamp())
        
        logger.info(
            "Chargeback metrics update completed",
            duration_seconds=round(duration, 2),
        )
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        worker_job_execution_total.labels(
            job_name="chargeback_metrics_updater",
            status="failed",
        ).inc()
        worker_job_duration_seconds.labels(
            job_name="chargeback_metrics_updater",
        ).observe(duration)
        
        logger.exception(
            "Failed to update chargeback metrics",
            error=str(e),
            duration_seconds=round(duration, 2),
        )
        raise


def run_chargeback_metrics_job() -> None:
    """
    Job entry point for APScheduler.
    
    Creates database session and runs metrics update.
    """
    db = next(get_db())
    try:
        update_chargeback_metrics(db)
    finally:
        db.close()


if __name__ == "__main__":
    # For testing/manual execution
    run_chargeback_metrics_job()
