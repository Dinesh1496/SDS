"""
SQLAlchemy ORM models.

All models are imported here so that Alembic's autogenerate can discover
them through ``app.models`` without requiring individual file imports.
"""

from app.models.cluster import Cluster, Monitor, Manager, OSD, RGW, CapacityHistory
from app.models.node import Node, NodeMetric
from app.models.storage import Tenant, Bucket, BucketUsage, TenantUsage
from app.models.monitoring import Alert, PlacementGroup
from app.models.reporting import Report
from app.models.chargeback import Chargeback, Forecast
from app.models.user import User, AuditLog
from app.models.settings import Setting

__all__ = [
    # Cluster
    "Cluster",
    "Monitor",
    "Manager",
    "OSD",
    "RGW",
    "CapacityHistory",
    # Node
    "Node",
    "NodeMetric",
    # Storage
    "Tenant",
    "Bucket",
    "BucketUsage",
    "TenantUsage",
    # Monitoring
    "Alert",
    "PlacementGroup",
    # Reporting
    "Report",
    # Chargeback
    "Chargeback",
    "Forecast",
    # User & Audit
    "User",
    "AuditLog",
    # Settings
    "Setting",
]
