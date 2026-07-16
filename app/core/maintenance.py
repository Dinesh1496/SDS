"""
Maintenance window management for alert suppression.

Allows operators to define scheduled or ad-hoc maintenance windows during
which alerts are suppressed to prevent noise during known system changes.
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import maintenance_window_active
from app.db.session import get_db

if TYPE_CHECKING:
    from app.models.settings import MaintenanceWindow

logger = get_logger(__name__)


class MaintenanceType(str, enum.Enum):
    """Type of maintenance window."""
    SCHEDULED = "scheduled"      # Planned maintenance
    EMERGENCY = "emergency"       # Unplanned emergency work
    TESTING = "testing"           # Testing/validation work


def is_maintenance_active(cluster_id: int, db: Session) -> bool:
    """
    Check if there is an active maintenance window for the given cluster.
    
    Args:
        cluster_id: The cluster ID to check
        db: Database session
    
    Returns:
        True if maintenance window is currently active, False otherwise
    """
    from app.models.settings import MaintenanceWindow
    
    now = datetime.utcnow()
    
    stmt = select(MaintenanceWindow).where(
        MaintenanceWindow.cluster_id == cluster_id,
        MaintenanceWindow.start_time <= now,
        MaintenanceWindow.end_time >= now,
        MaintenanceWindow.is_active == True,  # noqa: E712
    )
    
    result = db.execute(stmt).scalar_one_or_none()
    
    is_active = result is not None
    
    # Update Prometheus metric
    from app.models.cluster import Cluster
    cluster = db.get(Cluster, cluster_id)
    if cluster:
        maintenance_window_active.labels(
            cluster_name=cluster.name
        ).set(1 if is_active else 0)
    
    return is_active


def should_suppress_alert(
    cluster_id: int,
    alert_source: str,
    db: Session,
) -> bool:
    """
    Determine if an alert should be suppressed due to active maintenance.
    
    Args:
        cluster_id: The cluster ID
        alert_source: Source of the alert (e.g., "cluster_health", "osd")
        db: Database session
    
    Returns:
        True if the alert should be suppressed, False otherwise
    """
    if not is_maintenance_active(cluster_id, db):
        return False
    
    from app.models.settings import MaintenanceWindow
    
    now = datetime.utcnow()
    
    # Get active maintenance window
    stmt = select(MaintenanceWindow).where(
        MaintenanceWindow.cluster_id == cluster_id,
        MaintenanceWindow.start_time <= now,
        MaintenanceWindow.end_time >= now,
        MaintenanceWindow.is_active == True,  # noqa: E712
    )
    
    window = db.execute(stmt).scalar_one_or_none()
    
    if not window:
        return False
    
    # If no specific sources are configured, suppress all alerts
    if not window.suppress_alert_sources:
        return True
    
    # Check if this alert source should be suppressed
    suppressed_sources = [s.strip() for s in window.suppress_alert_sources.split(",")]
    return alert_source in suppressed_sources or "*" in suppressed_sources


def create_maintenance_window(
    cluster_id: int,
    start_time: datetime,
    end_time: datetime,
    reason: str,
    maintenance_type: MaintenanceType = MaintenanceType.SCHEDULED,
    created_by: str = "system",
    suppress_alert_sources: str | None = None,
    db: Session | None = None,
) -> MaintenanceWindow:
    """
    Create a new maintenance window.
    
    Args:
        cluster_id: The cluster ID
        start_time: When maintenance starts
        end_time: When maintenance ends
        reason: Reason for maintenance
        maintenance_type: Type of maintenance
        created_by: User who created the window
        suppress_alert_sources: Comma-separated list of alert sources to suppress (None = all)
        db: Database session (optional, will create if not provided)
    
    Returns:
        The created MaintenanceWindow instance
    """
    from app.models.settings import MaintenanceWindow
    
    if end_time <= start_time:
        raise ValueError("End time must be after start time")
    
    should_close_db = False
    if db is None:
        db = next(get_db())
        should_close_db = True
    
    try:
        window = MaintenanceWindow(
            cluster_id=cluster_id,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            maintenance_type=maintenance_type.value,
            created_by=created_by,
            suppress_alert_sources=suppress_alert_sources or "*",
            is_active=True,
        )
        
        db.add(window)
        db.commit()
        db.refresh(window)
        
        logger.info(
            "Created maintenance window",
            window_id=window.id,
            cluster_id=cluster_id,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            maintenance_type=maintenance_type.value,
        )
        
        return window
    finally:
        if should_close_db:
            db.close()


def end_maintenance_window(
    window_id: int,
    db: Session | None = None,
) -> bool:
    """
    Manually end a maintenance window before its scheduled end time.
    
    Args:
        window_id: The maintenance window ID
        db: Database session (optional)
    
    Returns:
        True if window was ended, False if not found
    """
    from app.models.settings import MaintenanceWindow
    
    should_close_db = False
    if db is None:
        db = next(get_db())
        should_close_db = True
    
    try:
        window = db.get(MaintenanceWindow, window_id)
        
        if not window:
            return False
        
        window.is_active = False
        window.end_time = datetime.utcnow()
        
        db.commit()
        
        logger.info(
            "Ended maintenance window early",
            window_id=window_id,
            cluster_id=window.cluster_id,
        )
        
        return True
    finally:
        if should_close_db:
            db.close()


def cleanup_expired_windows(db: Session) -> int:
    """
    Mark expired maintenance windows as inactive.
    
    This should be called periodically (e.g., every hour) to clean up
    windows that have passed their end time.
    
    Args:
        db: Database session
    
    Returns:
        Number of windows cleaned up
    """
    from app.models.settings import MaintenanceWindow
    
    now = datetime.utcnow()
    
    stmt = select(MaintenanceWindow).where(
        MaintenanceWindow.end_time < now,
        MaintenanceWindow.is_active == True,  # noqa: E712
    )
    
    expired_windows = db.execute(stmt).scalars().all()
    
    for window in expired_windows:
        window.is_active = False
    
    if expired_windows:
        db.commit()
        logger.info(f"Cleaned up {len(expired_windows)} expired maintenance windows")
    
    return len(expired_windows)
