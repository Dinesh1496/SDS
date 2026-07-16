"""
Object storage ORM models.

Tables:
  - tenants       — RGW tenants (accounts)
  - buckets       — S3 buckets per tenant
  - bucket_usage  — time-series bucket size/object-count snapshots
  - tenant_usage  — daily tenant-level aggregated usage
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class QuotaStatus(str, enum.Enum):
    UNDER = "under"
    WARNING = "warning"     # > 75% of quota
    CRITICAL = "critical"   # > 90% of quota
    EXCEEDED = "exceeded"
    NO_QUOTA = "no_quota"


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------

class Tenant(Base, TimestampMixin):
    """
    Represents a RGW tenant (billing account).

    Maps one-to-one to a Ceph RadosGW user/tenant. Contains quota
    configuration and the latest usage figures for fast lookups.
    """

    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("cluster_id", "tenant_id", name="uq_tenant_cluster_id"),
        Index("ix_tenants_cluster_id", "cluster_id"),
        Index("ix_tenants_tenant_id", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(256), nullable=False,
        doc="RGW tenant ID / user ID as returned by the admin API",
    )
    display_name: Mapped[str] = mapped_column(String(512), nullable=False)
    email: Mapped[str | None] = mapped_column(String(512), nullable=True)
    department: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cost_centre: Mapped[str | None] = mapped_column(
        String(128), nullable=True, doc="Internal cost centre code for chargeback"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Quota configuration (bytes; 0 = unlimited)
    quota_max_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    quota_max_objects: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    quota_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Latest usage snapshot (denormalised for fast reporting queries)
    current_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    current_objects: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    quota_status: Mapped[QuotaStatus] = mapped_column(
        Enum(QuotaStatus, name="quota_status"), nullable=False, default=QuotaStatus.NO_QUOTA
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="tenants")  # type: ignore[name-defined]
    buckets: Mapped[list["Bucket"]] = relationship(
        "Bucket", back_populates="tenant", cascade="all, delete-orphan"
    )
    usage_history: Mapped[list["TenantUsage"]] = relationship(
        "TenantUsage", back_populates="tenant", cascade="all, delete-orphan"
    )
    chargebacks: Mapped[list["Chargeback"]] = relationship(  # type: ignore[name-defined]
        "Chargeback", back_populates="tenant"
    )


# ---------------------------------------------------------------------------
# Bucket
# ---------------------------------------------------------------------------

class Bucket(Base, TimestampMixin):
    """
    Represents an S3 bucket owned by a tenant.

    Stores the latest size, object count, quota settings, and versioning
    status. Time-series history is in BucketUsage.
    """

    __tablename__ = "buckets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_bucket_tenant_name"),
        Index("ix_buckets_tenant_id", "tenant_id"),
        Index("ix_buckets_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False, doc="S3 bucket name")
    owner: Mapped[str] = mapped_column(String(256), nullable=False, doc="RGW owner user ID")
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    versioning_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Quota (bytes; 0 = unlimited)
    quota_max_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    quota_max_objects: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    quota_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Latest snapshot values (denormalised)
    current_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    current_objects: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    current_size_gb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quota_status: Mapped[QuotaStatus] = mapped_column(
        Enum(QuotaStatus, name="quota_status"), nullable=False, default=QuotaStatus.NO_QUOTA
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="buckets")
    usage_history: Mapped[list["BucketUsage"]] = relationship(
        "BucketUsage", back_populates="bucket", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# BucketUsage
# ---------------------------------------------------------------------------

class BucketUsage(Base):
    """
    Time-series usage snapshot for a single bucket.

    Immutable rows — inserted on each collection run.
    Used for growth trend charts and capacity forecasting.
    """

    __tablename__ = "bucket_usage"
    __table_args__ = (
        Index("ix_bucket_usage_bucket_recorded", "bucket_id", "recorded_at"),
        Index("ix_bucket_usage_recorded_at", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("buckets.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    size_gb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    object_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Delta from previous snapshot (null on first record)
    delta_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delta_objects: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    growth_rate_gb_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)

    bucket: Mapped["Bucket"] = relationship("Bucket", back_populates="usage_history")


# ---------------------------------------------------------------------------
# TenantUsage
# ---------------------------------------------------------------------------

class TenantUsage(Base):
    """
    Daily aggregated usage snapshot per tenant.

    One row per tenant per day. Aggregated from BucketUsage by the
    daily reporting job. Used for chargeback calculations.
    """

    __tablename__ = "tenant_usage"
    __table_args__ = (
        UniqueConstraint("tenant_id", "usage_date", name="uq_tenant_usage_date"),
        Index("ix_tenant_usage_tenant_id", "tenant_id"),
        Index("ix_tenant_usage_date", "usage_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    usage_date: Mapped[datetime] = mapped_column(
        Date, nullable=False, doc="The calendar date this record covers"
    )
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_size_gb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_objects: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bucket_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    peak_size_gb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="usage_history")


# Resolve forward reference for chargeback relationship
from app.models.chargeback import Chargeback  # noqa: E402, F401
from app.models.cluster import Cluster        # noqa: E402, F401
