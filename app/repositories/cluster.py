"""
Cluster repository — data access for clusters, monitors, managers, OSDs,
RGWs, and capacity history.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func

from app.models.cluster import (
    Cluster,
    ClusterHealthStatus,
    CapacityHistory,
    Monitor,
    Manager,
    OSD,
    OSDState,
    RGW,
)
from app.repositories.base import BaseRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClusterRepository(BaseRepository[Cluster, int]):
    """Repository for Cluster model CRUD and cluster-specific queries."""

    model = Cluster

    # ------------------------------------------------------------------
    # Cluster queries
    # ------------------------------------------------------------------

    def get_by_name(self, name: str) -> Cluster | None:
        """Fetch a cluster by its unique machine-readable name."""
        return self.get_one_by(name=name, deleted_at=None)

    def list_active(self) -> list[Cluster]:
        """Return all clusters that are active and not soft-deleted."""
        stmt = (
            select(Cluster)
            .where(Cluster.is_active.is_(True))
            .where(Cluster.deleted_at.is_(None))
            .order_by(Cluster.name)
        )
        return list(self._db.scalars(stmt).all())

    def update_health_status(
        self,
        cluster: Cluster,
        status: ClusterHealthStatus,
        detail: str | None = None,
    ) -> Cluster:
        """Update cluster health status and mark last-checked timestamp."""
        return self.update(
            cluster,
            health_status=status,
            health_detail=detail,
            last_checked_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Capacity history
    # ------------------------------------------------------------------

    def get_latest_capacity(self, cluster_id: int) -> CapacityHistory | None:
        """Return the most recent capacity snapshot for a cluster."""
        stmt = (
            select(CapacityHistory)
            .where(CapacityHistory.cluster_id == cluster_id)
            .order_by(CapacityHistory.recorded_at.desc())
            .limit(1)
        )
        return self._db.scalar(stmt)

    def get_capacity_history(
        self,
        cluster_id: int,
        since: datetime | None = None,
        limit: int = 168,   # 7 days at hourly
    ) -> list[CapacityHistory]:
        """
        Return capacity history for a cluster ordered by timestamp ascending.

        Args:
            cluster_id: Cluster primary key.
            since: If provided, only return records on or after this timestamp.
            limit: Maximum number of records to return.
        """
        stmt = (
            select(CapacityHistory)
            .where(CapacityHistory.cluster_id == cluster_id)
        )
        if since:
            stmt = stmt.where(CapacityHistory.recorded_at >= since)
        stmt = stmt.order_by(CapacityHistory.recorded_at.asc()).limit(limit)
        return list(self._db.scalars(stmt).all())

    def insert_capacity_snapshot(self, snapshot: CapacityHistory) -> CapacityHistory:
        """Insert a new capacity snapshot row."""
        return self.create(snapshot)

    # ------------------------------------------------------------------
    # OSD queries
    # ------------------------------------------------------------------

    def get_osds_by_cluster(self, cluster_id: int) -> list[OSD]:
        """Return all OSDs for a cluster."""
        stmt = select(OSD).where(OSD.cluster_id == cluster_id).order_by(OSD.osd_id)
        return list(self._db.scalars(stmt).all())

    def count_osds_down(self, cluster_id: int) -> int:
        """Count OSDs that are down (any down state)."""
        stmt = (
            select(func.count())
            .select_from(OSD)
            .where(OSD.cluster_id == cluster_id)
            .where(OSD.state.in_([OSDState.DOWN_IN, OSDState.DOWN_OUT]))
        )
        return self._db.scalar(stmt) or 0

    def upsert_osd(self, cluster_id: int, osd_id: int, **kwargs) -> OSD:
        """
        Insert or update an OSD record.

        If an OSD with the given cluster_id + osd_id exists, update it;
        otherwise insert a new row.
        """
        stmt = select(OSD).where(
            OSD.cluster_id == cluster_id,
            OSD.osd_id == osd_id,
        )
        existing = self._db.scalar(stmt)
        if existing:
            return self.update(existing, **kwargs)
        osd = OSD(cluster_id=cluster_id, osd_id=osd_id, **kwargs)
        return self.create(osd)

    # ------------------------------------------------------------------
    # Monitor queries
    # ------------------------------------------------------------------

    def get_monitors_by_cluster(self, cluster_id: int) -> list[Monitor]:
        stmt = select(Monitor).where(Monitor.cluster_id == cluster_id)
        return list(self._db.scalars(stmt).all())

    def upsert_monitor(self, cluster_id: int, name: str, **kwargs) -> Monitor:
        existing = self.get_one_by(cluster_id=cluster_id, name=name)
        if existing:
            return self.update(existing, **kwargs)
        mon = Monitor(cluster_id=cluster_id, name=name, **kwargs)
        return self.create(mon)

    # ------------------------------------------------------------------
    # Manager queries
    # ------------------------------------------------------------------

    def get_managers_by_cluster(self, cluster_id: int) -> list[Manager]:
        stmt = select(Manager).where(Manager.cluster_id == cluster_id)
        return list(self._db.scalars(stmt).all())

    def upsert_manager(self, cluster_id: int, name: str, **kwargs) -> Manager:
        existing = self.get_one_by(cluster_id=cluster_id, name=name)
        if existing:
            return self.update(existing, **kwargs)
        mgr = Manager(cluster_id=cluster_id, name=name, **kwargs)
        return self.create(mgr)

    # ------------------------------------------------------------------
    # RGW queries
    # ------------------------------------------------------------------

    def get_rgws_by_cluster(self, cluster_id: int) -> list[RGW]:
        stmt = select(RGW).where(RGW.cluster_id == cluster_id)
        return list(self._db.scalars(stmt).all())
