"""Integration tests for the health check endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthEndpoints:
    def test_health_check_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_liveness_probe(self, client: TestClient) -> None:
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_probe_with_db(self, client: TestClient) -> None:
        # With test SQLite DB, this should succeed
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
