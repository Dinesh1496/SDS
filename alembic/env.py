"""
Alembic environment configuration.

Reads database URL from application settings rather than alembic.ini,
ensuring consistent configuration across all environments.
Supports both offline (SQL script) and online (direct DB) migration modes.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the project root is on sys.path so 'app' is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db.base import Base

# Import all models so Alembic autogenerate can detect them
import app.models  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------

alembic_config = context.config

# Interpret alembic.ini logging configuration if present
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# Use the application database URL (overrides alembic.ini value)
settings = get_settings()
db_cfg = settings.get_db_settings()
alembic_config.set_main_option("sqlalchemy.url", db_cfg.url)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.

    Generates SQL scripts suitable for DBA review before applying.
    """
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against a live database connection.

    Uses a connection pool to apply migrations and generates a transaction
    per migration script.
    """
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # Single connection for migration scripts
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Include schemas — useful if future multi-schema support is added
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
