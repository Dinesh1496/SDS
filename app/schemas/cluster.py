"""
Pydantic schemas for Cluster API.

Separates the API contract (what clients send/receive) from the ORM model
(what the database stores). All schemas use `from_attributes=True` to
support construction from SQLAlchemy model instances.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.cluster import ClusterHealthStatus


class ClusterBase(BaseModel):
    """Fields shared across create and response schemas."""

    name: str = Field(..., min_length=1, max_length=128, description="Unique cluster identifier")
    display_name: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(default=None)
    admin_node: str = Field(..., description="Admin node hostname/IP")
    monitor_host: str = Field(..., description="Primary monitor hostname/IP")
    ssh_user: str = Field(default="cephadmin", max_length=64)
    ssh_key_path: str = Field(..., max_length=512)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    rgw_endpoint: str | None = Field(default=None)
    is_active: bool = Field(default=True)


class ClusterCreate(ClusterBase):
    """Schema for registering a new cluster. Excludes sensitive credential fields."""
    pass


class ClusterUpdate(BaseModel):
    """Schema for partial cluster updates — all fields optional."""

    display_name: str | None = Field(default=None, max_length=256)
    description: str | None = None
    admin_node: str | None = None
    monitor_host: str | None = None
    ssh_user: str | None = Field(default=None, max_length=64)
    ssh_key_path: str | None = Field(default=None, max_length=512)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    rgw_endpoint: str | None = None
    is_active: bool | None = None


class ClusterResponse(ClusterBase):
    """Full cluster response — includes server-assigned fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    health_status: ClusterHealthStatus
    health_detail: str | None = None
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Never expose SSH keys or secrets in API responses
    ssh_key_path: str = Field(exclude=True, default="")  # type: ignore[assignment]
    rgw_access_key: str | None = Field(exclude=True, default=None)
    rgw_secret_key: str | None = Field(exclude=True, default=None)


class ClusterListResponse(BaseModel):
    """Paginated list response for clusters."""

    clusters: list[ClusterResponse]
    total: int = Field(default=0)

    def model_post_init(self, __context: Any) -> None:  # type: ignore[override]
        self.total = len(self.clusters)


from typing import Any  # noqa: E402
