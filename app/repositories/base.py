"""
Generic repository base class.

Implements the Repository pattern: all database access goes through a
repository, never directly from service or API layers. This keeps
persistence concerns isolated and simplifies unit testing via mocking.

Usage::

    class ClusterRepository(BaseRepository[Cluster, int]):
        ...

    repo = ClusterRepository(db_session)
    cluster = repo.get_by_id(1)
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base, SoftDeleteMixin
from app.core.logging import get_logger

logger = get_logger(__name__)

# Generic type variables
ModelType = TypeVar("ModelType", bound=Base)
PKType = TypeVar("PKType")  # Primary key type (int, str, uuid, etc.)


class BaseRepository(Generic[ModelType, PKType]):
    """
    Generic CRUD repository.

    Subclasses must set ``model`` to the SQLAlchemy model class they manage.

    Args:
        db: SQLAlchemy Session (injected via FastAPI Depends or context manager).
    """

    model: type[ModelType]

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, pk: PKType) -> ModelType | None:
        """
        Fetch a single record by primary key.

        Returns None if the record does not exist or has been soft-deleted.
        """
        instance = self._db.get(self.model, pk)
        if instance is None:
            return None
        # Respect soft-delete mixin
        if isinstance(instance, SoftDeleteMixin) and instance.is_deleted:
            return None
        return instance

    def get_by_id_or_raise(self, pk: PKType) -> ModelType:
        """
        Fetch a single record by primary key, raising ValueError if not found.

        Raises:
            ValueError: If the record does not exist.
        """
        instance = self.get_by_id(pk)
        if instance is None:
            raise ValueError(
                f"{self.model.__name__} with id={pk!r} not found"
            )
        return instance

    def list_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
    ) -> list[ModelType]:
        """
        Return a paginated list of all active records.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            order_by: Column name to sort by (ascending). Prefix with '-' for descending.

        Returns:
            List of model instances.
        """
        stmt = select(self.model)

        # Exclude soft-deleted rows
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]

        # Ordering
        if order_by:
            descending = order_by.startswith("-")
            col_name = order_by.lstrip("-")
            col = getattr(self.model, col_name, None)
            if col is not None:
                stmt = stmt.order_by(col.desc() if descending else col.asc())

        stmt = stmt.offset(offset).limit(limit)
        return list(self._db.scalars(stmt).all())

    def count(self) -> int:
        """Return the total number of active (non-deleted) records."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return self._db.scalar(stmt) or 0

    def exists(self, pk: PKType) -> bool:
        """Return True if a record with the given primary key exists."""
        return self.get_by_id(pk) is not None

    def filter_by(self, **kwargs: Any) -> list[ModelType]:
        """
        Simple equality filter across one or more columns.

        Example::
            repo.filter_by(cluster_id=1, is_active=True)
        """
        stmt = select(self.model).filter_by(**kwargs)
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return list(self._db.scalars(stmt).all())

    def get_one_by(self, **kwargs: Any) -> ModelType | None:
        """Return the first record matching all equality conditions, or None."""
        results = self.filter_by(**kwargs)
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, instance: ModelType) -> ModelType:
        """
        Persist a new model instance.

        The session is flushed (not committed) so the instance receives its
        auto-generated PK. The calling transaction should commit.

        Args:
            instance: Populated model instance to insert.

        Returns:
            The persisted instance (with PK populated).
        """
        self._db.add(instance)
        self._db.flush()
        self._db.refresh(instance)
        logger.debug(
            "Created record",
            model=self.model.__name__,
            pk=getattr(instance, "id", None),
        )
        return instance

    def update(self, instance: ModelType, **kwargs: Any) -> ModelType:
        """
        Apply keyword argument updates to an existing model instance.

        Args:
            instance: The managed model instance to update.
            **kwargs: Column name → new value pairs.

        Returns:
            The updated instance.
        """
        for attr, value in kwargs.items():
            setattr(instance, attr, value)
        self._db.flush()
        self._db.refresh(instance)
        logger.debug(
            "Updated record",
            model=self.model.__name__,
            pk=getattr(instance, "id", None),
            fields=list(kwargs.keys()),
        )
        return instance

    def delete(self, instance: ModelType) -> None:
        """
        Delete a record — soft-delete if supported, hard-delete otherwise.

        Args:
            instance: The model instance to delete.
        """
        if isinstance(instance, SoftDeleteMixin):
            instance.soft_delete()
            self._db.flush()
            logger.debug(
                "Soft-deleted record",
                model=self.model.__name__,
                pk=getattr(instance, "id", None),
            )
        else:
            self._db.delete(instance)
            self._db.flush()
            logger.debug(
                "Hard-deleted record",
                model=self.model.__name__,
                pk=getattr(instance, "id", None),
            )

    def bulk_create(self, instances: list[ModelType]) -> list[ModelType]:
        """
        Efficiently insert multiple records in a single flush.

        Args:
            instances: List of populated model instances.

        Returns:
            The list of persisted instances.
        """
        self._db.add_all(instances)
        self._db.flush()
        for instance in instances:
            self._db.refresh(instance)
        logger.debug(
            "Bulk created records",
            model=self.model.__name__,
            count=len(instances),
        )
        return instances

    def refresh(self, instance: ModelType) -> ModelType:
        """Reload the instance from the database, discarding any pending changes."""
        self._db.refresh(instance)
        return instance
