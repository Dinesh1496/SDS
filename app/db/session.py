"""
Database session factory and dependency injection helpers.

Provides:
- ``engine`` — SQLAlchemy Engine (synchronous)
- ``SessionLocal`` — session factory
- ``get_db()`` — FastAPI dependency that yields a scoped session
- ``get_db_context()`` — context manager for non-request contexts (workers, scripts)
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
db_cfg = settings.get_db_settings()

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_engine(
    db_cfg.url,
    pool_size=db_cfg.pool_size,
    max_overflow=db_cfg.max_overflow,
    pool_timeout=db_cfg.pool_timeout,
    pool_recycle=db_cfg.pool_recycle,
    pool_pre_ping=True,          # Verify connection health before checkout
    echo=db_cfg.echo_sql,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_pg_session_params(dbapi_conn: Any, connection_record: Any) -> None:
    """Set PostgreSQL session-level parameters on new connections."""
    with dbapi_conn.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'UTC'")
        cursor.execute("SET application_name = 'sds-nexus-platform'")


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # Avoid lazy-load after commit in background workers
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for use in FastAPI endpoints.

    The session is automatically committed on success and rolled back on
    exception, then closed regardless of outcome.

    Usage::

        @router.get("/clusters")
        def list_clusters(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Context manager for background workers and scripts
# ---------------------------------------------------------------------------

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager that provides a database session outside of FastAPI.

    Suitable for use in background workers, Celery tasks, and one-off scripts.

    Usage::

        with get_db_context() as db:
            repo = ClusterRepository(db)
            clusters = repo.list_active()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
        logger.debug("Database session committed successfully")
    except Exception as exc:
        db.rollback()
        logger.error("Database session rolled back", error=str(exc))
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health check helper
# ---------------------------------------------------------------------------

def check_db_connectivity() -> bool:
    """
    Verify that the database is reachable.

    Used by the /health endpoint and application startup checks.

    Returns:
        True if the database responds to a SELECT 1 query, False otherwise.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database connectivity check failed", error=str(exc))
        return False


# Avoid a bare ``Any`` import error at module level when type-checking
from typing import Any  # noqa: E402 — intentional late import for event listener typing
