"""
User management and audit log ORM models.

Tables:
  - users      — platform users with roles
  - audit_logs — immutable record of all user and system actions
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"             # Full platform access
    OPS = "ops"                 # Operations team — read/write
    VIEWER = "viewer"           # Read-only access
    BILLING = "billing"         # Chargeback & reports only


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base, TimestampMixin, SoftDeleteMixin):
    """
    Platform user account.

    Passwords are stored as bcrypt hashes. JWT tokens reference the user's
    UUID (stored as a string) rather than the auto-increment primary key
    to allow for future account migration.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_email", "email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.VIEWER
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.ACTIVE
    )
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", passive_deletes=True
    )


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """
    Immutable audit trail for all user and system actions.

    Rows are never updated or deleted (retained for compliance). The
    ``performed_by`` field stores the username string so the log remains
    readable even if the user account is later deleted.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="NULL for system-generated actions",
    )
    performed_by: Mapped[str] = mapped_column(
        String(128), nullable=False,
        doc="Username or 'system' for automated actions",
    )
    action: Mapped[str] = mapped_column(
        String(128), nullable=False,
        doc="Action verb, e.g. 'create_report', 'acknowledge_alert', 'login'",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        doc="Resource type acted upon, e.g. 'cluster', 'tenant', 'report'",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        doc="ID or name of the resource acted upon",
    )
    details: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        doc="Arbitrary JSON payload with action-specific details",
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")
