"""
Pytest configuration and shared fixtures.

Provides:
- In-memory SQLite database for unit tests (no Postgres required)
- FastAPI test client
- Factory fixtures for creating test data
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables before importing app modules
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-min-32-chars-padding")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-min-32-chars-padding")
os.environ.setdefault("DB_PASSWORD", "test-password")
os.environ.setdefault("CEPH_MONITOR_HOST", "test-monitor")
os.environ.setdefault("CEPH_ADMIN_NODE", "test-admin")
os.environ.setdefault("CEPH_SSH_KEY_PATH", "/tmp/test_key")
os.environ.setdefault("RGW_ENDPOINT", "http://localhost:7480")
os.environ.setdefault("RGW_ACCESS_KEY", "test-access-key")
os.environ.setdefault("RGW_SECRET_KEY", "test-secret-key")
os.environ.setdefault("RGW_ADMIN_ENDPOINT", "http://localhost:7480/admin")
os.environ.setdefault("RGW_ADMIN_ACCESS_KEY", "test-admin-access")
os.environ.setdefault("RGW_ADMIN_SECRET_KEY", "test-admin-secret")
os.environ.setdefault("SMTP_HOST", "localhost")
os.environ.setdefault("SMTP_USER", "test@example.com")
os.environ.setdefault("SMTP_PASSWORD", "test-password")
os.environ.setdefault("SMTP_FROM_ADDRESS", "test@example.com")
os.environ.setdefault("APP_ENV", "development")

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.cluster import Cluster, ClusterHealthStatus
from app.models.user import User, UserRole
from app.core.security import hash_password

# ---------------------------------------------------------------------------
# Test database (SQLite in-memory)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all tables once for the test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """
    Provide a clean database session for each test.

    Uses savepoints to roll back after each test, keeping the schema
    intact between tests without recreating tables.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Provide a FastAPI TestClient with the test database injected.

    Overrides the get_db dependency to use the test session.
    """
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_cluster(db_session: Session) -> Cluster:
    """Create and persist a sample cluster for use in tests."""
    cluster = Cluster(
        name="test-cluster-01",
        display_name="Test Cluster 01",
        admin_node="admin.test.internal",
        monitor_host="mon.test.internal",
        ssh_user="cephadmin",
        ssh_key_path="/tmp/test_key",
        health_status=ClusterHealthStatus.HEALTH_OK,
        is_active=True,
    )
    db_session.add(cluster)
    db_session.flush()
    return cluster


@pytest.fixture()
def admin_user(db_session: Session) -> User:
    """Create and persist an admin user for authenticated test requests."""
    user = User(
        username="testadmin",
        email="testadmin@example.com",
        full_name="Test Administrator",
        hashed_password=hash_password("TestPassword123!"),
        role=UserRole.ADMIN,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.flush()
    return user
