"""
Database initialisation script.

Run once after `alembic upgrade head` to seed the database with:
- Default admin user
- Default platform settings
- Optionally register the first cluster from environment variables

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --seed-cluster
"""

from __future__ import annotations

import argparse
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_db_context
from app.models.user import User, UserRole
from app.models.settings import Setting
from app.models.cluster import Cluster
from app.core.security import hash_password

configure_logging(level="INFO", log_format="text")
logger = get_logger(__name__)


DEFAULT_SETTINGS: list[dict] = [
    # Chargeback
    {"category": "chargeback", "key": "gbp_per_gb_month", "value": "0.05", "value_type": "float",
     "description": "Cost per GB per month in GBP"},
    {"category": "chargeback", "key": "usd_per_gb_month", "value": "0.06", "value_type": "float",
     "description": "Cost per GB per month in USD"},
    {"category": "chargeback", "key": "gbp_usd_rate", "value": "1.27", "value_type": "float",
     "description": "GBP to USD exchange rate"},
    {"category": "chargeback", "key": "vat_rate", "value": "0.20", "value_type": "float",
     "description": "VAT rate (20%)"},
    {"category": "chargeback", "key": "billing_day", "value": "1", "value_type": "int",
     "description": "Day of month for billing cycle"},
    # Alerts
    {"category": "alerts", "key": "capacity_warning_percent", "value": "75", "value_type": "float",
     "description": "Capacity warning threshold (%)"},
    {"category": "alerts", "key": "capacity_critical_percent", "value": "85", "value_type": "float",
     "description": "Capacity critical threshold (%)"},
    {"category": "alerts", "key": "osd_down_threshold", "value": "1", "value_type": "int",
     "description": "Number of OSDs down before alerting"},
    # Reporting
    {"category": "reporting", "key": "retention_days", "value": "365", "value_type": "int",
     "description": "Days to retain generated reports"},
    {"category": "reporting", "key": "daily_email_time", "value": "07:00", "value_type": "string",
     "description": "Daily email report send time (HH:MM 24h)"},
]


def create_admin_user(db_session) -> None:
    """Create the default admin user if it doesn't exist."""
    existing = db_session.query(User).filter(User.username == "admin").first()
    if existing:
        logger.info("Admin user already exists — skipping")
        return

    admin = User(
        username="admin",
        email="admin@sds-nexus.internal",
        full_name="Platform Administrator",
        hashed_password=hash_password("ChangeMe123!"),
        role=UserRole.ADMIN,
        is_superuser=True,
    )
    db_session.add(admin)
    logger.info("Default admin user created (username: admin, password: ChangeMe123!)")
    logger.warning("IMPORTANT: Change the admin password immediately after first login!")


def seed_default_settings(db_session) -> None:
    """Insert default platform settings if they don't exist."""
    inserted = 0
    for setting_data in DEFAULT_SETTINGS:
        existing = (
            db_session.query(Setting)
            .filter(
                Setting.category == setting_data["category"],
                Setting.key == setting_data["key"],
            )
            .first()
        )
        if not existing:
            db_session.add(Setting(**setting_data))
            inserted += 1
    logger.info(f"Settings seeded: {inserted} new settings inserted")


def register_first_cluster(db_session) -> None:
    """Register the first cluster from environment variables."""
    settings = get_settings()
    ceph_cfg = settings.get_ceph_settings()

    existing = db_session.query(Cluster).filter(
        Cluster.name == ceph_cfg.cluster_name
    ).first()

    if existing:
        logger.info(f"Cluster '{ceph_cfg.cluster_name}' already registered — skipping")
        return

    try:
        cluster = Cluster(
            name=ceph_cfg.cluster_name,
            display_name=ceph_cfg.cluster_display_name,
            admin_node=ceph_cfg.admin_node,
            monitor_host=ceph_cfg.monitor_host,
            ssh_user=ceph_cfg.ssh_user,
            ssh_key_path=ceph_cfg.ssh_key_path,
            ssh_port=ceph_cfg.ssh_port,
        )
        db_session.add(cluster)
        logger.info(
            f"Cluster registered",
            cluster_name=ceph_cfg.cluster_name,
            admin_node=ceph_cfg.admin_node,
        )
    except Exception as exc:
        logger.error(f"Failed to register cluster: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialise the SDS Nexus database")
    parser.add_argument(
        "--seed-cluster",
        action="store_true",
        help="Register the first cluster from environment variables",
    )
    args = parser.parse_args()

    logger.info("Starting database initialisation")

    with get_db_context() as db:
        create_admin_user(db)
        seed_default_settings(db)
        if args.seed_cluster:
            register_first_cluster(db)

    logger.info("Database initialisation complete")


if __name__ == "__main__":
    main()
