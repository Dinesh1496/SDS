"""
Ceph command client.

Wraps SSH-based Ceph CLI commands and returns typed Python structures.
All Ceph interactions go through this client, never via ad-hoc SSH calls
from services. This isolates the Ceph CLI interface behind a single,
testable boundary.

Usage::

    with CephClient.from_cluster(cluster) as ceph:
        status = ceph.get_status()
        df = ceph.get_df()
        osds = ceph.get_osd_tree()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.utils.ssh_client import SSHClient

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes for parsed Ceph output
# ---------------------------------------------------------------------------

@dataclass
class CephStatusSummary:
    """Parsed summary from `ceph status --format json`."""

    health_status: str          # HEALTH_OK | HEALTH_WARN | HEALTH_ERR
    health_checks: dict[str, Any] = field(default_factory=dict)
    num_monitors: int = 0
    monitors_in_quorum: int = 0
    num_osds: int = 0
    osds_up: int = 0
    osds_in: int = 0
    num_pgs: int = 0
    pgs_active_clean: int = 0
    pgs_degraded: int = 0
    pgs_recovering: int = 0
    total_bytes: int = 0
    used_bytes: int = 0
    available_bytes: int = 0
    read_bytes_sec: int = 0
    write_bytes_sec: int = 0
    read_ops_sec: int = 0
    write_ops_sec: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CephDFSummary:
    """Parsed output from `ceph df --format json`."""

    total_bytes: int = 0
    total_avail_bytes: int = 0
    total_used_raw_bytes: int = 0
    total_objects: int = 0
    pools: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OSDInfo:
    """Single OSD entry from `ceph osd tree --format json`."""

    osd_id: int
    name: str
    host: str
    state: str          # up/in, down/in, etc.
    weight: float
    crush_weight: float
    device_class: str | None
    capacity_bytes: int | None
    used_bytes: int | None


# ---------------------------------------------------------------------------
# Ceph Client
# ---------------------------------------------------------------------------

class CephClient:
    """
    Client for executing Ceph CLI commands over SSH.

    All commands are run as JSON output (--format json) to ensure
    reliable, schema-stable parsing rather than screen-scraping.

    Args:
        ssh: An open SSHClient instance.
        ceph_bin: Path to the ceph binary (default: /usr/bin/ceph).
    """

    def __init__(
        self,
        ssh: SSHClient,
        ceph_bin: str = "/usr/bin/ceph",
    ) -> None:
        self._ssh = ssh
        self._ceph_bin = ceph_bin

    @classmethod
    def from_cluster(
        cls,
        host: str,
        username: str,
        key_path: str,
        port: int = 22,
        timeout: int = 30,
    ) -> "CephClient":
        """
        Factory method — creates and connects an SSH client, returns CephClient.

        Note: Use as a context manager to ensure the SSH connection is closed::

            with CephClient.from_cluster(...) as ceph:
                status = ceph.get_status()
        """
        ssh = SSHClient(
            host=host,
            username=username,
            key_path=key_path,
            port=port,
            timeout=timeout,
        )
        ssh.connect()
        instance = cls(ssh=ssh)
        instance._owns_ssh = True
        return instance

    def __enter__(self) -> "CephClient":
        return self

    def __exit__(self, *_: Any) -> None:
        if getattr(self, "_owns_ssh", False):
            self._ssh.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_ceph(self, subcommand: str, timeout: int = 60) -> Any:
        """
        Run a Ceph CLI command and return parsed JSON.

        Args:
            subcommand: Everything after 'ceph', e.g. 'status'.
            timeout: Command timeout in seconds.

        Returns:
            Parsed JSON output.

        Raises:
            RuntimeError: If the command fails.
            ValueError: If output cannot be parsed as JSON.
        """
        cmd = f"{self._ceph_bin} {subcommand} --format json 2>/dev/null"
        return self._ssh.run_json(cmd, timeout=timeout)

    # ------------------------------------------------------------------
    # Cluster status
    # ------------------------------------------------------------------

    def get_status(self) -> CephStatusSummary:
        """
        Collect full cluster status.

        Parses `ceph status --format json` into a CephStatusSummary.
        """
        logger.debug("Collecting ceph status")
        raw = self._run_ceph("status")

        health = raw.get("health", {})
        mon_status = raw.get("monmap", {})
        osd_map = raw.get("osdmap", {})
        pg_map = raw.get("pgmap", {})
        client_io = pg_map.get("read_bytes_sec", 0)

        # Parse PG state counts
        pgs_active_clean = 0
        pgs_degraded = 0
        pgs_recovering = 0
        for pg_state in pg_map.get("pgs_by_state", []):
            state_name: str = pg_state.get("state_name", "")
            count: int = pg_state.get("count", 0)
            if "active+clean" in state_name:
                pgs_active_clean += count
            if "degraded" in state_name:
                pgs_degraded += count
            if "recovering" in state_name or "backfilling" in state_name:
                pgs_recovering += count

        return CephStatusSummary(
            health_status=health.get("status", "UNKNOWN"),
            health_checks=health.get("checks", {}),
            num_monitors=len(mon_status.get("mons", [])),
            monitors_in_quorum=len(mon_status.get("quorum", [])),
            num_osds=osd_map.get("num_osds", 0),
            osds_up=osd_map.get("num_up_osds", 0),
            osds_in=osd_map.get("num_in_osds", 0),
            num_pgs=pg_map.get("num_pgs", 0),
            pgs_active_clean=pgs_active_clean,
            pgs_degraded=pgs_degraded,
            pgs_recovering=pgs_recovering,
            total_bytes=pg_map.get("bytes_total", 0),
            used_bytes=pg_map.get("bytes_used", 0),
            available_bytes=pg_map.get("bytes_avail", 0),
            read_bytes_sec=pg_map.get("read_bytes_sec", 0),
            write_bytes_sec=pg_map.get("write_bytes_sec", 0),
            read_ops_sec=pg_map.get("read_op_per_sec", 0),
            write_ops_sec=pg_map.get("write_op_per_sec", 0),
            raw=raw,
        )

    def get_df(self) -> CephDFSummary:
        """
        Collect cluster-level capacity statistics.

        Parses `ceph df --format json`.
        """
        logger.debug("Collecting ceph df")
        raw = self._run_ceph("df")

        stats = raw.get("stats", {})
        return CephDFSummary(
            total_bytes=stats.get("total_bytes", 0),
            total_avail_bytes=stats.get("total_avail_bytes", 0),
            total_used_raw_bytes=stats.get("total_used_raw_bytes", 0),
            total_objects=stats.get("total_objects", 0),
            pools=raw.get("pools", []),
        )

    def get_osd_tree(self) -> list[OSDInfo]:
        """
        Collect OSD layout and state information.

        Parses `ceph osd tree --format json` and flattens the CRUSH tree
        into a list of OSD entries with host assignments.
        """
        logger.debug("Collecting ceph osd tree")
        raw = self._run_ceph("osd tree")

        nodes: list[dict] = raw.get("nodes", [])
        # Build host lookup: id -> hostname
        host_lookup: dict[int, str] = {}
        for node in nodes:
            if node.get("type") == "host":
                for child_id in node.get("children", []):
                    host_lookup[child_id] = node.get("name", "unknown")

        osds: list[OSDInfo] = []
        for node in nodes:
            if node.get("type") != "osd":
                continue
            osd_id = node.get("id", -1)
            # Derive state string
            is_up = node.get("status") == "up"
            is_in = node.get("reweight", 0) > 0
            if is_up and is_in:
                state = "up/in"
            elif is_up and not is_in:
                state = "up/out"
            elif not is_up and is_in:
                state = "down/in"
            else:
                state = "down/out"

            osds.append(OSDInfo(
                osd_id=osd_id,
                name=node.get("name", f"osd.{osd_id}"),
                host=host_lookup.get(osd_id, "unknown"),
                state=state,
                weight=float(node.get("reweight", 1.0)),
                crush_weight=float(node.get("crush_weight", 1.0)),
                device_class=node.get("device_class"),
                capacity_bytes=None,   # populated from `ceph osd df`
                used_bytes=None,
            ))

        return osds

    def get_osd_df(self) -> dict[int, dict[str, Any]]:
        """
        Collect per-OSD disk usage.

        Returns a dict keyed by OSD ID with capacity/usage data.
        """
        logger.debug("Collecting ceph osd df")
        raw = self._run_ceph("osd df")
        result: dict[int, dict[str, Any]] = {}
        for node in raw.get("nodes", []):
            osd_id = node.get("id")
            if osd_id is not None:
                result[osd_id] = {
                    "capacity_bytes": node.get("kb", 0) * 1024,
                    "used_bytes": node.get("kb_used", 0) * 1024,
                    "available_bytes": node.get("kb_avail", 0) * 1024,
                    "utilization_percent": node.get("utilization", 0.0),
                }
        return result

    def get_pg_stat(self) -> dict[str, Any]:
        """Return raw PG statistics from `ceph pg stat`."""
        return self._run_ceph("pg stat")

    def get_health_detail(self) -> dict[str, Any]:
        """Return detailed health information from `ceph health detail`."""
        return self._run_ceph("health detail")

    def get_mon_stat(self) -> dict[str, Any]:
        """Return monitor statistics from `ceph mon stat`."""
        return self._run_ceph("mon stat")

    def get_mgr_stat(self) -> dict[str, Any]:
        """Return manager statistics from `ceph mgr stat`."""
        return self._run_ceph("mgr stat")
