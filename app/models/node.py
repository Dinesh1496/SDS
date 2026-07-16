"""
Node monitoring ORM models.

Tables:
  - nodes        — physical/virtual nodes in a Ceph cluster
  - node_metrics — time-series metric snapshots per node
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
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class NodeRole(str, enum.Enum):
    MON = "mon"
    MGR = "mgr"
    OSD = "osd"
    RGW = "rgw"
    MDS = "mds"
    ADMIN = "admin"
    MIXED = "mixed"


class NodeStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class SMARTStatus(str, enum.Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class Node(Base, TimestampMixin):
    """
    Represents a physical or virtual node in a Ceph cluster.

    A node may have multiple roles (e.g. OSD + MON on small clusters).
    Hardware specs and network information are stored here; time-series
    metrics are stored in NodeMetric.
    """

    __tablename__ = "nodes"
    __table_args__ = (
        Index("ix_nodes_cluster_id", "cluster_id"),
        Index("ix_nodes_hostname", "hostname"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    hostname: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    fqdn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role: Mapped[NodeRole] = mapped_column(
        Enum(NodeRole, name="node_role"), nullable=False, default=NodeRole.OSD
    )
    status: Mapped[NodeStatus] = mapped_column(
        Enum(NodeStatus, name="node_status"), nullable=False, default=NodeStatus.UNKNOWN
    )

    # Hardware specs (populated at discovery, rarely changes)
    cpu_cores: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cpu_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    total_memory_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kernel_version: Mapped[str | None] = mapped_column(String(128), nullable=True)

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="nodes")  # type: ignore[name-defined]
    metrics: Mapped[list["NodeMetric"]] = relationship(
        "NodeMetric", back_populates="node", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# NodeMetric
# ---------------------------------------------------------------------------

class NodeMetric(Base):
    """
    Time-series metric snapshot for a node.

    Each row represents one collection run. Rows are immutable — never
    updated. Old rows are pruned by the data retention job.
    """

    __tablename__ = "node_metrics"
    __table_args__ = (
        Index("ix_node_metrics_node_recorded", "node_id", "recorded_at"),
        Index("ix_node_metrics_recorded_at", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # CPU
    cpu_usage_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_load_1m: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_load_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_load_15m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Memory
    memory_total_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    memory_used_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    memory_available_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    memory_used_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    swap_total_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    swap_used_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Network (aggregate for all interfaces)
    net_bytes_sent: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_bytes_recv: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_packets_sent: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_packets_recv: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Temperature (max across all sensors)
    max_cpu_temp_celsius: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_disk_temp_celsius: Mapped[float | None] = mapped_column(Float, nullable=True)

    # SMART summary
    smart_status: Mapped[SMARTStatus] = mapped_column(
        Enum(SMARTStatus, name="smart_status"), nullable=False, default=SMARTStatus.UNKNOWN
    )
    smart_failed_drives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Raw disk stats (JSON list of per-device metrics for detailed drill-down)
    disk_stats: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        doc="List of dicts: [{device, total_bytes, used_bytes, used_pct, temp_c, smart_status}]",
    )

    # Network interface stats (JSON)
    net_interface_stats: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        doc="Dict keyed by interface name: {bytes_sent, bytes_recv, speed_mbps}",
    )

    node: Mapped["Node"] = relationship("Node", back_populates="metrics")


# Resolve forward reference from cluster.py
from app.models.cluster import Cluster  # noqa: E402, F401
