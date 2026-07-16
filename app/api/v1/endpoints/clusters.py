"""
Cluster management API endpoints.

Provides CRUD operations for cluster registration and read access
to cluster health status. Write operations require OPS or ADMIN role.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import DBSession, CurrentUser, require_ops_or_admin, require_admin
from app.models.cluster import Cluster, ClusterHealthStatus
from app.repositories.cluster import ClusterRepository
from app.schemas.cluster import (
    ClusterCreate,
    ClusterUpdate,
    ClusterResponse,
    ClusterListResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=ClusterListResponse, summary="List all clusters")
def list_clusters(db: DBSession, current_user: CurrentUser) -> ClusterListResponse:
    """Return all active (non-deleted) clusters."""
    repo = ClusterRepository(db)
    clusters = repo.list_active()
    logger.info("Clusters listed", user=current_user.username, count=len(clusters))
    return ClusterListResponse(clusters=[ClusterResponse.model_validate(c) for c in clusters])


@router.get("/{cluster_id}", response_model=ClusterResponse, summary="Get cluster by ID")
def get_cluster(cluster_id: int, db: DBSession, current_user: CurrentUser) -> ClusterResponse:
    """Return a single cluster by its primary key."""
    repo = ClusterRepository(db)
    cluster = repo.get_by_id(cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")
    return ClusterResponse.model_validate(cluster)


@router.post(
    "",
    response_model=ClusterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new cluster",
    dependencies=[require_ops_or_admin],
)
def create_cluster(
    payload: ClusterCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> ClusterResponse:
    """Register a new Ceph cluster in the platform."""
    repo = ClusterRepository(db)

    # Check for name uniqueness
    if repo.get_by_name(payload.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A cluster named '{payload.name}' already exists.",
        )

    cluster = Cluster(**payload.model_dump())
    cluster = repo.create(cluster)

    logger.info(
        "Cluster registered",
        cluster_id=cluster.id,
        cluster_name=cluster.name,
        user=current_user.username,
    )
    return ClusterResponse.model_validate(cluster)


@router.patch(
    "/{cluster_id}",
    response_model=ClusterResponse,
    summary="Update cluster settings",
    dependencies=[require_ops_or_admin],
)
def update_cluster(
    cluster_id: int,
    payload: ClusterUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> ClusterResponse:
    """Update a cluster's configuration. Only provided fields are updated."""
    repo = ClusterRepository(db)
    cluster = repo.get_by_id(cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")

    update_data = payload.model_dump(exclude_unset=True)
    cluster = repo.update(cluster, **update_data)
    logger.info(
        "Cluster updated",
        cluster_id=cluster_id,
        fields=list(update_data.keys()),
        user=current_user.username,
    )
    return ClusterResponse.model_validate(cluster)


@router.delete(
    "/{cluster_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a cluster",
    dependencies=[require_admin],
)
def delete_cluster(
    cluster_id: int,
    db: DBSession,
    current_user: CurrentUser,
) -> None:
    """Soft-delete a cluster from the platform."""
    repo = ClusterRepository(db)
    cluster = repo.get_by_id(cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")

    repo.delete(cluster)
    logger.info(
        "Cluster soft-deleted",
        cluster_id=cluster_id,
        user=current_user.username,
    )
