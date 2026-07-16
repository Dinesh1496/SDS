"""
Cluster-level ORM models.

Tables:
  - clusters          — registered Ceph clusters
  - monitors          — MON daemons per cluster
  - managers          — MGR daemons per cluster
  - osds              — OSD daemons per cluster
  - rgws              — RADOS Gateway instances per cluster
  - capacity_history  — hourly capacity snapshots per cluster
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ClusterHealthStatus(str, enum.Enum):
    HEALTH_OK = "HEALTH_OK"
    HEALTH_WARN = "HEALTH_WARN"
    HEALTH_ERR = "HEALTH_ERR"
    UNKNOWN = "UNKNOWN"


class DaemonStatus(str, enum.Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class OSDState(str, enum.Enum):
    UP_IN = "up/in"
    UP_OUT = "up/out"
    DOWN_IN = "down/in"
    DOWN_OUT = "down/out"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Cluster
# ---------------------------------------------------------------------------

class Cluster(Base, TimestampMixin, SoftDeleteMixin):
    """
    Represents a registered Ceph cluster.

    Supports multiple clusters per platform deployment. Each cluster has
    its own set of monitors, managers, OSDs, and RGW instances.
    """

    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True,
        doc="Unique machine-readable cluster name (e.g. 'prod-cluster-01')",
    )
    display_name: Mapped[str] = mapped_column(
        String(256), nullable=False,
        doc="Human-readable cluster name shown in reports and dashboards",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_node: Mapped[str] = mapped_column(
        String(256), nullable=False,
        doc="Hostname or IP of the Ceph admin node used for SSH commands",
    )
    monitor_host: Mapped[str] = mapped_column(
        String(256), nullable=False,
        doc="Primary MON hostname or IP for API access",
    )
    ssh_user: Mapped[str] = mapped_column(String(64), nullable=False, default="cephadmin")
    ssh_key_path: Mapped[str] = mapped_column(
        String(512), nullable=False,
        doc="Absolute path to SSH private key on the platform host",
    )
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    rgw_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rgw_access_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    rgw_secret_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Latest health snapshot (updated by health collector)
    health_status: Mapped[ClusterHealthStatus] = mapped_column(
        Enum(ClusterHealthStatus, name="cluster_health_status"),
        nullable=False,
        default=ClusterHealthStatus.UNKNOWN,
    )
    health_detail: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Raw health detail string from 'ceph status'",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    monitors: Mapped[list["Monitor"]] = relationship(
        "Monitor", back_populates="cluster", cascade="all, delete-orphan"
    )
    managers: Mapped[list["Manager"]] = relationship(
        "Manager", back_populates="cluster", cascade="all, delete-orphan"
    )
    osds: Mapped[list["OSD"]] = relationship(
        "OSD", back_populates="cluster", cascade="all, delete-orphan"
    )
    rgws: Mapped[list["RGW"]] = relationship(
        "RGW", back_populates="cluster", cascade="all, delete-orphan"
    )
    nodes: Mapped[list["Node"]] = relationship(  # type: ignore[name-defined]
        "Node", back_populates="cluster", cascade="all, delete-orphan"
    )
    capacity_history: Mapped[list["CapacityHistory"]] = relationship(
        "CapacityHistory", back_populates="cluster", cascade="all, delete-orphan"
    )
    tenants: Mapped[list["Tenant"]] = relationship(  # type: ignore[name-defined]
        "Tenant", back_populates="cluster", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(  # type: ignore[name-defined]
        "Alert", back_populates="cluster", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

class Monitor(Base, TimestampMixin):
    """Represents a single Ceph MON daemon."""

    __tablename__ = "monitors"
    __table_args__ = (
        UniqueConstraint("cluster_id", "name", name="uq_monitor_cluster_name"),
        Index("ix_monitors_cluster_id", "cluster_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, doc="MON name, e.g. 'mon.a'")
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=6789)
    status: Mapped[DaemonStatus] = mapped_column(
        Enum(DaemonStatus, name="daemon_status"), nullable=False, default=DaemonStatus.UNKNOWN
    )
    in_quorum: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="monitors")


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class Manager(Base, TimestampMixin):
    """Represents a single Ceph MGR daemon."""

    __tablename__ = "managers"
    __table_args__ = (
        UniqueConstraint("cluster_id", "name", name="uq_manager_cluster_name"),
        Index("ix_managers_cluster_id", "cluster_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, doc="MGR name, e.g. 'mgr.a'")
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[DaemonStatus] = mapped_column(
        Enum(DaemonStatus, name="daemon_status"),
        nullable=False,
        default=DaemonStatus.UNKNOWN,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="True if this is the active (not standby) MGR"
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="managers")


# ---------------------------------------------------------------------------
# OSD
# ---------------------------------------------------------------------------

class OSD(Base, TimestampMixin):
    """
    Represents a single Ceph OSD daemon.

    Tracks state (up/in/out/down), weight, device class, and capacity.
    """

    __tablename__ = "osds"
    __table_args__ = (
        UniqueConstraint("cluster_id", "osd_id", name="uq_osd_cluster_osd_id"),
        Index("ix_osds_cluster_id", "cluster_id"),
        Index("ix_osds_status", "state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    osd_id: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="Ceph OSD numeric ID (osd.N)"
    )
    host: Mapped[str] = mapped_column(String(256), nullable=False, doc="Host running this OSD")
    state: Mapped[OSDState] = mapped_column(
        Enum(OSDState, name="osd_state"), nullable=False, default=OSDState.UNKNOWN
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    crush_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    device_class: Mapped[str | None] = mapped_column(
        String(32), nullable=True, doc="Device class: hdd, ssd, nvme"
    )
    capacity_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    used_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="osds")


# ---------------------------------------------------------------------------
# RGW
# ---------------------------------------------------------------------------

class RGW(Base, TimestampMixin):
    """Represents a RADOS Gateway instance."""

    __tablename__ = "rgws"
    __table_args__ = (
        UniqueConstraint("cluster_id", "name", name="uq_rgw_cluster_name"),
        Index("ix_rgws_cluster_id", "cluster_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=7480)
    zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[DaemonStatus] = mapped_column(
        Enum(DaemonStatus, name="daemon_status"), nullable=False, default=DaemonStatus.UNKNOWN
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="rgws")


# ---------------------------------------------------------------------------
# CapacityHistory
# ---------------------------------------------------------------------------

class CapacityHistory(Base):
    """
    Hourly capacity snapshot for a cluster.

    Immutable — rows are inserted, never updated. Used for trend analysis,
    growth forecasting, and chargeback calculations.
    """

    __tablename__ = "capacity_history"
    __table_args__ = (
        Index("ix_capacity_history_cluster_recorded", "cluster_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp when this snapshot was taken",
    )

    # Raw byte counts from 'ceph df'
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_percent: Mapped[float] = mapped_column(Float, nullable=False)

    # Object counts
    total_objects: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Derived metrics
    total_gb: Mapped[float] = mapped_column(Float, nullable=False)
    used_gb: Mapped[float] = mapped_column(Float, nullable=False)
    available_gb: Mapped[float] = mapped_column(Float, nullable=False)

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="capacity_history")


# Avoid circular import at module level — Node and Alert are defined elsewhere
from app.models.node import Node          # noqa: E402, F401
from app.models.storage import Tenant     # noqa: E402, F401
from app.models.monitoring import Alert   # noqa: E402, F401
