"""
SQLAlchemy declarative base and common model mixins.

All ORM models inherit from Base. Mixins provide shared columns
(timestamps, soft-delete, etc.) to avoid repetition across models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Declarative base class for all SQLAlchemy ORM models.

    Provides a __tablename__ convention and a default __repr__ for debugging.
    """

    def __repr__(self) -> str:
        """Human-readable representation showing primary key columns."""
        pk_cols = [col.name for col in self.__table__.primary_key.columns]
        pk_vals = {col: getattr(self, col, None) for col in pk_cols}
        return f"<{self.__class__.__name__} {pk_vals}>"

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary of column values (shallow copy)."""
        return {col.name: getattr(self, col.name) for col in self.__table__.columns}


class TimestampMixin:
    """
    Adds ``created_at`` and ``updated_at`` columns to any model.

    Both columns are timezone-aware and managed automatically by the database.
    ``updated_at`` is refreshed on every UPDATE via an ``onupdate`` trigger.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="UTC timestamp when the row was first inserted.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="UTC timestamp of the most recent update.",
    )


class SoftDeleteMixin:
    """
    Adds soft-delete support via a ``deleted_at`` nullable column.

    Rows with ``deleted_at IS NOT NULL`` are considered logically deleted.
    Repository queries should filter these out by default.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="UTC timestamp when the row was soft-deleted; NULL = active.",
    )

    @property
    def is_deleted(self) -> bool:
        """Return True if this record has been soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark this record as soft-deleted with the current UTC timestamp."""
        self.deleted_at = datetime.now(timezone.utc)
