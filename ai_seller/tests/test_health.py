"""Health check tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Test client fixture."""
    return TestClient(app)


class TestHealthCheck:
    """Health check endpoint tests."""

    def test_health_check(self, client: TestClient):
        """Test basic health check."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs" in data
        assert "health" in data

    def test_api_docs_redirect(self, client: TestClient):
        """Test API docs redirect."""
        response = client.get("/api/docs")
        
        assert response.status_code == 200
        # Should return Swagger UI HTML
        assert "swagger" in response.text.lower()

    def test_api_redoc(self, client: TestClient):
        """Test API ReDoc."""
        response = client.get("/api/redoc")
        
        assert response.status_code == 200
        # Should return ReDoc HTML
        assert "redoc" in response.text.lower()

    def test_api_openapi_json(self, client: TestClient):
        """Test OpenAPI JSON schema."""
        response = client.get("/api/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "AI Seller"


class TestDetailedHealthCheck:
    """Detailed health check tests."""

    def test_detailed_health_check(self, client: TestClient):
        """Test detailed health check."""
        response = client.get("/api/v1/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "database" in data["components"]
        assert "version" in data
