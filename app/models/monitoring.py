"""
Monitoring and alerting ORM models.

Tables:
  - alerts            — generated alerts and their lifecycle states
  - placement_groups  — PG state snapshots per cluster
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertSource(str, enum.Enum):
    CLUSTER_HEALTH = "cluster_health"
    OSD = "osd"
    NODE = "node"
    CAPACITY = "capacity"
    PG = "placement_group"
    TENANT = "tenant"
    BUCKET = "bucket"
    SYSTEM = "system"


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class Alert(Base, TimestampMixin):
    """
    Represents a platform-generated alert.

    Alerts are raised by monitoring collectors and resolved when the
    underlying condition clears. Unresolved alerts drive email notifications.
    """

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_cluster_id", "cluster_id"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[AlertSource] = mapped_column(
        Enum(AlertSource, name="alert_source"), nullable=False
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"), nullable=False, default=AlertStatus.ACTIVE
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional reference to the affected resource
    resource_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="e.g. 'osd', 'node', 'bucket'"
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True, doc="ID or name of the affected resource"
    )

    # Deduplication key — same alert won't be created if an active one exists
    dedup_key: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)

    # Lifecycle timestamps
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notification_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="alerts")  # type: ignore[name-defined]


# ---------------------------------------------------------------------------
# PlacementGroup
# ---------------------------------------------------------------------------

class PlacementGroup(Base):
    """
    Placement Group (PG) state snapshot.

    One row per collection run, representing the aggregate PG state counts
    for a cluster. Used for trend analysis and health status derivation.
    """

    __tablename__ = "placement_groups"
    __table_args__ = (
        Index("ix_pg_cluster_recorded", "cluster_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    total_pgs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_clean: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    degraded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    undersized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    misplaced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recovering: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backfilling: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stale: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Percentages for quick dashboard queries
    active_clean_percent: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    degraded_percent: Mapped[float] = mapped_column(Integer, nullable=False, default=0)


# Resolve forward reference
from app.models.cluster import Cluster  # noqa: E402, F401
