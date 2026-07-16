"""
Platform settings ORM model.

Table:
  - settings — key/value store for runtime-configurable platform settings.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Setting(Base, TimestampMixin):
    """
    Key/value store for runtime-configurable platform settings.

    Used for settings that operators need to change without redeploying
    the application (e.g. chargeback rates, alert thresholds, report
    schedules). Type information is stored in ``value_type`` to allow
    proper deserialisation.
    """

    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("category", "key", name="uq_setting_category_key"),
        Index("ix_settings_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False,
        doc="Grouping category, e.g. 'chargeback', 'alerts', 'reporting'",
    )
    key: Mapped[str] = mapped_column(
        String(128), nullable=False,
        doc="Setting key, e.g. 'gbp_per_gb_month'",
    )
    value: Mapped[str] = mapped_column(
        Text, nullable=False,
        doc="String-serialised value; deserialise using value_type",
    )
    value_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="string",
        doc="Python type hint: string | int | float | bool | json",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Human-readable description of what this setting controls",
    )
    is_secret: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0,
        doc="If 1, value is encrypted at rest and masked in API responses",
    )

    def get_typed_value(self) -> str | int | float | bool | dict:
        """Deserialise the string value to its declared Python type."""
        import json as _json

        match self.value_type:
            case "int":
                return int(self.value)
            case "float":
                return float(self.value)
            case "bool":
                return self.value.lower() in ("true", "1", "yes")
            case "json":
                return _json.loads(self.value)
            case _:
                return self.value


# ---------------------------------------------------------------------------
# MaintenanceWindow
# ---------------------------------------------------------------------------

class MaintenanceWindow(Base, TimestampMixin):
    """
    Maintenance window for alert suppression.
    
    Allows operators to schedule maintenance periods during which alerts
    can be suppressed to prevent noise during system changes.
    """
    
    __tablename__ = "maintenance_windows"
    __table_args__ = (
        Index("ix_maint_window_cluster_times", "cluster_id", "start_time", "end_time"),
        Index("ix_maint_window_active", "is_active"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    cluster_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Cluster ID this maintenance window applies to",
    )
    
    start_time: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Maintenance start time (ISO 8601 format)",
    )
    
    end_time: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Maintenance end time (ISO 8601 format)",
    )
    
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Reason for maintenance",
    )
    
    maintenance_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="scheduled",
        doc="Type: scheduled, emergency, testing",
    )
    
    created_by: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="system",
        doc="User who created this window",
    )
    
    suppress_alert_sources: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        doc="Comma-separated list of alert sources to suppress (* = all)",
    )
    
    is_active: Mapped[bool] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Whether this window is currently active (can be manually disabled)",
    )
