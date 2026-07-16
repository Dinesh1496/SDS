"""
Prometheus metrics instrumentation.

Exposes application and business metrics to Prometheus for monitoring
and alerting via Grafana dashboards.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Response

# ---------------------------------------------------------------------------
# Application Info
# ---------------------------------------------------------------------------

app_info = Info("sds_nexus_app", "Application information")


# ---------------------------------------------------------------------------
# HTTP Metrics
# ---------------------------------------------------------------------------

http_requests_total = Counter(
    "sds_nexus_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "sds_nexus_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_requests_in_progress = Gauge(
    "sds_nexus_http_requests_in_progress",
    "Number of HTTP requests in progress",
    ["method", "endpoint"],
)


# ---------------------------------------------------------------------------
# Ceph Cluster Health Metrics
# ---------------------------------------------------------------------------

ceph_cluster_health_status = Gauge(
    "ceph_cluster_health_status",
    "Ceph cluster health status (0=OK, 1=WARN, 2=ERR)",
    ["cluster_name"],
)

ceph_cluster_total_bytes = Gauge(
    "ceph_cluster_total_bytes",
    "Total cluster capacity in bytes",
    ["cluster_name"],
)

ceph_cluster_used_bytes = Gauge(
    "ceph_cluster_used_bytes",
    "Used cluster capacity in bytes",
    ["cluster_name"],
)

ceph_cluster_available_bytes = Gauge(
    "ceph_cluster_available_bytes",
    "Available cluster capacity in bytes",
    ["cluster_name"],
)

ceph_cluster_utilization_percent = Gauge(
    "ceph_cluster_utilization_percent",
    "Cluster capacity utilization percentage",
    ["cluster_name"],
)


# ---------------------------------------------------------------------------
# OSD Metrics
# ---------------------------------------------------------------------------

ceph_osd_total = Gauge(
    "ceph_osd_total",
    "Total number of OSDs in the cluster",
    ["cluster_name"],
)

ceph_osd_up = Gauge(
    "ceph_osd_up",
    "Number of OSDs in UP state",
    ["cluster_name"],
)

ceph_osd_in = Gauge(
    "ceph_osd_in",
    "Number of OSDs in IN state",
    ["cluster_name"],
)

ceph_osd_down = Gauge(
    "ceph_osd_down",
    "Number of OSDs in DOWN state",
    ["cluster_name"],
)

ceph_osd_out = Gauge(
    "ceph_osd_out",
    "Number of OSDs in OUT state",
    ["cluster_name"],
)


# ---------------------------------------------------------------------------
# MON Metrics
# ---------------------------------------------------------------------------

ceph_mon_total = Gauge(
    "ceph_mon_total",
    "Total number of MON nodes",
    ["cluster_name"],
)

ceph_mon_in_quorum = Gauge(
    "ceph_mon_in_quorum",
    "Number of MON nodes in quorum",
    ["cluster_name"],
)


# ---------------------------------------------------------------------------
# Placement Group Metrics
# ---------------------------------------------------------------------------

ceph_pg_total = Gauge(
    "ceph_pg_total",
    "Total number of placement groups",
    ["cluster_name"],
)

ceph_pg_active_clean = Gauge(
    "ceph_pg_active_clean",
    "Number of placement groups in active+clean state",
    ["cluster_name"],
)

ceph_pg_degraded = Gauge(
    "ceph_pg_degraded",
    "Number of degraded placement groups",
    ["cluster_name"],
)

ceph_pg_undersized = Gauge(
    "ceph_pg_undersized",
    "Number of undersized placement groups",
    ["cluster_name"],
)

ceph_pg_misplaced = Gauge(
    "ceph_pg_misplaced",
    "Number of misplaced placement groups",
    ["cluster_name"],
)

ceph_pg_recovering = Gauge(
    "ceph_pg_recovering",
    "Number of recovering placement groups",
    ["cluster_name"],
)


# ---------------------------------------------------------------------------
# Node Metrics
# ---------------------------------------------------------------------------

ceph_node_cpu_usage_percent = Gauge(
    "ceph_node_cpu_usage_percent",
    "Node CPU utilization percentage",
    ["cluster_name", "node_name"],
)

ceph_node_memory_usage_percent = Gauge(
    "ceph_node_memory_usage_percent",
    "Node memory utilization percentage",
    ["cluster_name", "node_name"],
)

ceph_node_load_average_1m = Gauge(
    "ceph_node_load_average_1m",
    "Node 1-minute load average",
    ["cluster_name", "node_name"],
)

ceph_node_load_average_5m = Gauge(
    "ceph_node_load_average_5m",
    "Node 5-minute load average",
    ["cluster_name", "node_name"],
)

ceph_node_load_average_15m = Gauge(
    "ceph_node_load_average_15m",
    "Node 15-minute load average",
    ["cluster_name", "node_name"],
)

ceph_node_temperature_celsius = Gauge(
    "ceph_node_temperature_celsius",
    "Node CPU temperature in Celsius",
    ["cluster_name", "node_name", "sensor"],
)


# ---------------------------------------------------------------------------
# Object Storage (RGW) Metrics
# ---------------------------------------------------------------------------

rgw_bucket_total = Gauge(
    "rgw_bucket_total",
    "Total number of RGW buckets",
    ["cluster_name"],
)

rgw_bucket_objects = Gauge(
    "rgw_bucket_objects",
    "Number of objects in bucket",
    ["cluster_name", "bucket_name", "tenant"],
)

rgw_bucket_size_bytes = Gauge(
    "rgw_bucket_size_bytes",
    "Bucket size in bytes",
    ["cluster_name", "bucket_name", "tenant"],
)

rgw_user_total = Gauge(
    "rgw_user_total",
    "Total number of RGW users",
    ["cluster_name"],
)

rgw_user_bytes_sent = Counter(
    "rgw_user_bytes_sent_total",
    "Total bytes sent by user",
    ["cluster_name", "user_id"],
)

rgw_user_bytes_received = Counter(
    "rgw_user_bytes_received_total",
    "Total bytes received by user",
    ["cluster_name", "user_id"],
)

rgw_user_operations = Counter(
    "rgw_user_operations_total",
    "Total operations by user",
    ["cluster_name", "user_id", "operation_type"],
)


# ---------------------------------------------------------------------------
# Alert Metrics
# ---------------------------------------------------------------------------

alert_total = Gauge(
    "sds_nexus_alert_total",
    "Total number of alerts",
    ["cluster_name", "severity", "status"],
)

alert_created_total = Counter(
    "sds_nexus_alert_created_total",
    "Total number of alerts created",
    ["cluster_name", "source", "severity"],
)


# ---------------------------------------------------------------------------
# Chargeback Metrics
# ---------------------------------------------------------------------------

chargeback_monthly_cost_gbp = Gauge(
    "sds_nexus_chargeback_monthly_cost_gbp",
    "Monthly chargeback cost in GBP",
    ["cluster_name", "tenant"],
)

chargeback_monthly_cost_usd = Gauge(
    "sds_nexus_chargeback_monthly_cost_usd",
    "Monthly chargeback cost in USD",
    ["cluster_name", "tenant"],
)

chargeback_tenant_usage_bytes = Gauge(
    "sds_nexus_chargeback_tenant_usage_bytes",
    "Tenant storage usage in bytes",
    ["cluster_name", "tenant"],
)


# ---------------------------------------------------------------------------
# Database Metrics
# ---------------------------------------------------------------------------

db_connection_pool_size = Gauge(
    "sds_nexus_db_connection_pool_size",
    "Current size of database connection pool",
)

db_connection_pool_checked_out = Gauge(
    "sds_nexus_db_connection_pool_checked_out",
    "Number of connections currently checked out",
)

db_query_duration_seconds = Histogram(
    "sds_nexus_db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)


# ---------------------------------------------------------------------------
# Worker Metrics
# ---------------------------------------------------------------------------

worker_job_execution_total = Counter(
    "sds_nexus_worker_job_execution_total",
    "Total number of worker job executions",
    ["job_name", "status"],
)

worker_job_duration_seconds = Histogram(
    "sds_nexus_worker_job_duration_seconds",
    "Worker job execution duration in seconds",
    ["job_name"],
    buckets=(1, 5, 10, 30, 60, 300, 600, 1800),
)

worker_job_last_success_timestamp = Gauge(
    "sds_nexus_worker_job_last_success_timestamp",
    "Unix timestamp of last successful job execution",
    ["job_name"],
)


# ---------------------------------------------------------------------------
# Maintenance Window Metrics
# ---------------------------------------------------------------------------

maintenance_window_active = Gauge(
    "sds_nexus_maintenance_window_active",
    "Whether a maintenance window is currently active (1=active, 0=inactive)",
    ["cluster_name"],
)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def metrics_response() -> Response:
    """Return Prometheus metrics in the expected format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


def track_time(metric: Histogram, labels: dict | None = None):
    """
    Decorator to track function execution time.
    
    Usage:
        @track_time(worker_job_duration_seconds, {"job_name": "cluster_health"})
        def collect_cluster_health():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with metric.labels(**(labels or {})).time():
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with metric.labels(**(labels or {})).time():
                return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def set_app_info(version: str, environment: str, python_version: str) -> None:
    """Set application info metrics on startup."""
    app_info.info({
        "version": version,
        "environment": environment,
        "python_version": python_version,
    })
