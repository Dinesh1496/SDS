"""
Unit tests for the BaseRepository generic CRUD layer.

Uses the Cluster model as a concrete example — no mocking required since
tests run against the in-memory SQLite database provided by conftest.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.cluster import Cluster, ClusterHealthStatus
from app.repositories.cluster import ClusterRepository


class TestBaseRepository:
    """Tests for BaseRepository CRUD operations via ClusterRepository."""

    def test_create_returns_persisted_instance(self, db_session: Session) -> None:
        repo = ClusterRepository(db_session)
        cluster = Cluster(
            name="create-test",
            display_name="Create Test",
            admin_node="admin.local",
            monitor_host="mon.local",
            ssh_user="cephadmin",
            ssh_key_path="/tmp/key",
        )
        created = repo.create(cluster)
        assert created.id is not None
        assert created.name == "create-test"

    def test_get_by_id_returns_existing(self, db_session: Session, sample_cluster: Cluster) -> None:
        repo = ClusterRepository(db_session)
        found = repo.get_by_id(sample_cluster.id)
        assert found is not None
        assert found.id == sample_cluster.id

    def test_get_by_id_returns_none_for_missing(self, db_session: Session) -> None:
        repo = ClusterRepository(db_session)
        assert repo.get_by_id(99999) is None

    def test_get_by_id_or_raise_raises_for_missing(self, db_session: Session) -> None:
        repo = ClusterRepository(db_session)
        with pytest.raises(ValueError, match="not found"):
            repo.get_by_id_or_raise(99999)

    def test_update_applies_changes(self, db_session: Session, sample_cluster: Cluster) -> None:
        repo = ClusterRepository(db_session)
        updated = repo.update(sample_cluster, display_name="Updated Name")
        assert updated.display_name == "Updated Name"

    def test_soft_delete_sets_deleted_at(self, db_session: Session, sample_cluster: Cluster) -> None:
        repo = ClusterRepository(db_session)
        repo.delete(sample_cluster)
        assert sample_cluster.deleted_at is not None

    def test_soft_deleted_not_returned_by_get_by_id(
        self, db_session: Session, sample_cluster: Cluster
    ) -> None:
        repo = ClusterRepository(db_session)
        repo.delete(sample_cluster)
        assert repo.get_by_id(sample_cluster.id) is None

    def test_list_all_excludes_deleted(self, db_session: Session) -> None:
        repo = ClusterRepository(db_session)
        c1 = repo.create(Cluster(
            name="list-active", display_name="Active",
            admin_node="a", monitor_host="m", ssh_user="u", ssh_key_path="/k",
        ))
        c2 = repo.create(Cluster(
            name="list-deleted", display_name="Deleted",
            admin_node="a", monitor_host="m", ssh_user="u", ssh_key_path="/k",
        ))
        repo.delete(c2)
        all_clusters = repo.list_all()
        ids = [c.id for c in all_clusters]
        assert c1.id in ids
        assert c2.id not in ids

    def test_count_excludes_deleted(self, db_session: Session, sample_cluster: Cluster) -> None:
        repo = ClusterRepository(db_session)
        initial = repo.count()
        repo.delete(sample_cluster)
        assert repo.count() == initial - 1

    def test_exists_returns_true_for_existing(
        self, db_session: Session, sample_cluster: Cluster
    ) -> None:
        repo = ClusterRepository(db_session)
        assert repo.exists(sample_cluster.id) is True

    def test_exists_returns_false_for_missing(self, db_session: Session) -> None:
        repo = ClusterRepository(db_session)
        assert repo.exists(99999) is False


class TestClusterRepository:
    """Tests for ClusterRepository-specific methods."""

    def test_get_by_name_returns_cluster(
        self, db_session: Session, sample_cluster: Cluster
    ) -> None:
        repo = ClusterRepository(db_session)
        found = repo.get_by_name(sample_cluster.name)
        assert found is not None
        assert found.id == sample_cluster.id

    def test_get_by_name_returns_none_for_unknown(self, db_session: Session) -> None:
        repo = ClusterRepository(db_session)
        assert repo.get_by_name("nonexistent-cluster") is None

    def test_list_active_excludes_inactive(self, db_session: Session) -> None:
        repo = ClusterRepository(db_session)
        inactive = repo.create(Cluster(
            name="inactive-cluster", display_name="Inactive",
            admin_node="a", monitor_host="m", ssh_user="u", ssh_key_path="/k",
            is_active=False,
        ))
        active_clusters = repo.list_active()
        assert all(c.is_active for c in active_clusters)
        assert inactive.id not in [c.id for c in active_clusters]

    def test_update_health_status(
        self, db_session: Session, sample_cluster: Cluster
    ) -> None:
        repo = ClusterRepository(db_session)
        updated = repo.update_health_status(
            sample_cluster, ClusterHealthStatus.HEALTH_WARN, "mon is down"
        )
        assert updated.health_status == ClusterHealthStatus.HEALTH_WARN
        assert updated.health_detail == "mon is down"
        assert updated.last_checked_at is not None
